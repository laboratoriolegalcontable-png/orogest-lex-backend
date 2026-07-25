"""
OroGest Lex — Tests Phase 9-14
Memory chunking, encryption, due diligence, rate limiting.
"""

import pytest

from app.api.v1.endpoints.properties import compute_risk_level, get_dd_template
from app.memory.memory_service import chunk_text
from app.middleware.rate_limit import InMemoryRateLimiter, get_rate_limit_config
from app.services.encryption_service import decrypt_field, encrypt_field, is_encrypted


# ═══════════════════════════════════════════
# MEMORY — TEXT CHUNKING
# ═══════════════════════════════════════════
class TestChunking:
    def test_short_text_single_chunk(self):
        text = "Este es un texto corto."
        chunks = chunk_text(text, max_chars=1500)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_multiple_chunks(self):
        # Build a text longer than 1500 chars
        text = "\n\n".join([f"Párrafo {i}. " + "x" * 200 for i in range(20)])
        chunks = chunk_text(text, max_chars=500, overlap=0)
        assert len(chunks) > 1
        # Each chunk should be <= max_chars (approximately, with paragraph boundaries)
        for chunk in chunks:
            assert len(chunk) <= 700  # Allow some slack for paragraph boundaries

    def test_empty_text(self):
        chunks = chunk_text("", max_chars=1500)
        assert len(chunks) == 1
        assert chunks[0] == ""

    def test_overlap_adds_context(self):
        text = "Primer párrafo largo " * 50 + "\n\n" + "Segundo párrafo largo " * 50
        chunks_no_overlap = chunk_text(text, max_chars=500, overlap=0)
        chunks_with_overlap = chunk_text(text, max_chars=500, overlap=100)
        # Overlapped chunks should be longer (carrying prev context)
        if len(chunks_with_overlap) > 1:
            assert len(chunks_with_overlap[1]) > len(chunks_no_overlap[1])


# ═══════════════════════════════════════════
# ENCRYPTION — AES-256-GCM
# ═══════════════════════════════════════════
class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "Cliente: Juan Pérez — CUIT 20-12345678-9"
        encrypted = encrypt_field(plaintext)
        assert encrypted != plaintext
        decrypted = decrypt_field(encrypted)
        assert decrypted == plaintext

    def test_encrypt_empty_string(self):
        assert encrypt_field("") == ""
        assert decrypt_field("") == ""

    def test_different_encryptions_for_same_text(self):
        text = "Datos sensibles del imputado"
        e1 = encrypt_field(text)
        e2 = encrypt_field(text)
        # Different nonces → different ciphertexts
        assert e1 != e2
        # Both decrypt to same plaintext
        assert decrypt_field(e1) == text
        assert decrypt_field(e2) == text

    def test_is_encrypted_detection(self):
        encrypted = encrypt_field("test data")
        assert is_encrypted(encrypted)
        assert not is_encrypted("plain text")
        assert not is_encrypted("")
        assert not is_encrypted("short")

    def test_unicode_support(self):
        text = "Dirección: Av. Córdoba 1234, CABA — §123 del CCyCN — año 2026"
        encrypted = encrypt_field(text)
        decrypted = decrypt_field(encrypted)
        assert decrypted == text

    def test_large_text(self):
        text = "A" * 10000  # 10KB
        encrypted = encrypt_field(text)
        decrypted = decrypt_field(encrypted)
        assert decrypted == text


# ═══════════════════════════════════════════
# DUE DILIGENCE — RISK COMPUTATION
# ═══════════════════════════════════════════
class TestDueDiligence:
    def test_dd_template_arg(self):
        template = get_dd_template("ARG")
        assert "dominio_folio_real" in template
        assert "uif_pep_check" in template
        assert len(template) == 10

    def test_dd_template_esp(self):
        template = get_dd_template("ESP")
        assert "nota_simple" in template
        assert "plusvalia" in template
        assert len(template) == 6

    def test_dd_template_ury(self):
        template = get_dd_template("URY")
        assert "certificado_dominio" in template
        assert len(template) == 4

    def test_dd_template_unknown_defaults_to_arg(self):
        template = get_dd_template("XYZ")
        assert len(template) == 10

    def test_risk_all_pendiente_is_rojo(self):
        checklist = {
            "item1": {"status": "pendiente"},
            "item2": {"status": "pendiente"},
        }
        assert compute_risk_level(checklist) == "rojo"

    def test_risk_any_problema_is_rojo(self):
        checklist = {
            "item1": {"status": "ok"},
            "item2": {"status": "problema"},
            "item3": {"status": "ok"},
        }
        assert compute_risk_level(checklist) == "rojo"

    def test_risk_all_ok_is_verde(self):
        checklist = {
            "item1": {"status": "ok"},
            "item2": {"status": "ok"},
            "item3": {"status": "no_aplica"},
        }
        assert compute_risk_level(checklist) == "verde"

    def test_risk_some_pendiente_is_amarillo(self):
        checklist = {
            "item1": {"status": "ok"},
            "item2": {"status": "ok"},
            "item3": {"status": "ok"},
            "item4": {"status": "pendiente"},
        }
        assert compute_risk_level(checklist) == "amarillo"

    def test_risk_empty_is_rojo(self):
        assert compute_risk_level({}) == "rojo"
        assert compute_risk_level(None) == "rojo"


# ═══════════════════════════════════════════
# RATE LIMITING
# ═══════════════════════════════════════════
class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = InMemoryRateLimiter()
        for i in range(5):
            allowed, _ = limiter.check("test_key", max_requests=5, window_seconds=60)
            if i < 5:
                assert allowed

    def test_blocks_over_limit(self):
        limiter = InMemoryRateLimiter()
        for _ in range(10):
            limiter.check("block_key", max_requests=10, window_seconds=60)
        allowed, remaining = limiter.check("block_key", max_requests=10, window_seconds=60)
        assert not allowed
        assert remaining == 0

    def test_different_keys_independent(self):
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            limiter.check("key_a", max_requests=5, window_seconds=60)
        # key_a is exhausted
        allowed_a, _ = limiter.check("key_a", max_requests=5, window_seconds=60)
        assert not allowed_a
        # key_b is fresh
        allowed_b, _ = limiter.check("key_b", max_requests=5, window_seconds=60)
        assert allowed_b

    def test_rate_limit_config_ai(self):
        config = get_rate_limit_config("/api/v1/ai/query")
        assert config["max_requests"] == 30  # from settings

    def test_rate_limit_config_auth(self):
        config = get_rate_limit_config("/api/v1/auth/login")
        assert config["max_requests"] == 10
        assert config["window"] == 300

    def test_rate_limit_config_default(self):
        config = get_rate_limit_config("/api/v1/cases/")
        assert config["max_requests"] == 120


# ═══════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
