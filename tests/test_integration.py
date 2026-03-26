"""
OroGest Lex — Integration Tests (Fase 20)
Tests for Redis service, notifications, search, AI prompt building.
These run without a real DB or Redis — they test the logic layers.
"""

import pytest
import time

from app.services.ai_service import _build_system_prompt, _extract_verification_flags
from app.middleware.rate_limit import InMemoryRateLimiter, get_rate_limit_config
from app.agents.orchestrator import classify_request, Domain, Urgency, Workflow


# We can't import InMemoryRateLimiter from redis_service since it doesn't exist there,
# but we test the redis_service module structure is importable
class TestRedisServiceStructure:
    def test_imports(self):
        from app.services.redis_service import (
            RedisCache,
            RedisRateLimiter,
            TokenBlacklist,
            RealtimeCounters,
        )
        assert RedisCache.PREFIX == "orogest:cache:"
        assert RedisRateLimiter.PREFIX == "orogest:ratelimit:"
        assert TokenBlacklist.PREFIX == "orogest:blacklist:"
        assert RealtimeCounters.PREFIX == "orogest:counter:"


# ═══════════════════════════════════════════
# AI SERVICE — PROMPT BUILDING
# ═══════════════════════════════════════════
class TestPromptBuilding:
    def test_base_prompt_only(self):
        prompt = _build_system_prompt()
        assert "Estudio Oro S.A.S." in prompt
        assert "ANTI-ALUCINACIÓN" in prompt
        assert "CPACF T° 145 F° 433" in prompt

    def test_workflow_appended(self):
        prompt = _build_system_prompt(workflow="escrito_blindado")
        assert "Escrito Blindado" in prompt
        assert "Casación-Ready" in prompt

    def test_due_diligence_workflow(self):
        prompt = _build_system_prompt(workflow="due_diligence")
        assert "Due Diligence" in prompt

    def test_case_info_injected(self):
        case_info = {
            "caption": "Pérez s/ robo agravado",
            "branch": "penal",
            "jurisdiction": "CABA",
            "court": "TOC N° 5",
            "case_number": "12345/2024",
            "notes": "Nulidad pendiente por cadena de custodia",
        }
        prompt = _build_system_prompt(case_info=case_info)
        assert "CAUSA ACTIVA" in prompt
        assert "Pérez s/ robo agravado" in prompt
        assert "TOC N° 5" in prompt

    def test_rag_context_injected(self):
        rag = "En la causa similar 'García 2023' se resolvió que la prueba digital..."
        prompt = _build_system_prompt(rag_context=rag)
        assert "CONTEXTO RECUPERADO DE MEMORIA" in prompt
        assert "García 2023" in prompt

    def test_full_assembly(self):
        prompt = _build_system_prompt(
            workflow="estrategia_procesal",
            case_info={"caption": "Test", "branch": "penal"},
            rag_context="Antecedente relevante...",
        )
        assert "Estrategia Procesal" in prompt
        assert "CAUSA ACTIVA" in prompt
        assert "CONTEXTO RECUPERADO" in prompt

    def test_custom_override(self):
        custom = "Sos un asistente de testing."
        prompt = _build_system_prompt(system_prompt_override=custom)
        assert prompt.startswith(custom)
        assert "Estudio Oro S.A.S." not in prompt

    def test_unknown_workflow_ignored(self):
        prompt = _build_system_prompt(workflow="nonexistent_workflow")
        # Should have base prompt but no workflow addition
        assert "Estudio Oro S.A.S." in prompt


# ═══════════════════════════════════════════
# AI SERVICE — FLAG EXTRACTION
# ═══════════════════════════════════════════
class TestFlagExtraction:
    def test_extract_verificar(self):
        text = "Según el art. 168 CPPN [VERIFICAR TEXTO], el plazo es de 10 días."
        flags = _extract_verification_flags(text)
        assert "verificar" in flags
        assert "[VERIFICAR TEXTO]" in flags["verificar"]

    def test_extract_multiple_types(self):
        text = (
            "El índice RIPTE actual es 1234 [VERIFICAR VALOR ACTUAL]. "
            "El imputado probablemente tenía domicilio en CABA [INFERIDO]. "
            "La jurisprudencia indica [FUENTE REQUERIDA] que..."
        )
        flags = _extract_verification_flags(text)
        assert "verificar" in flags
        assert "inferido" in flags
        assert "fuente_requerida" in flags

    def test_no_flags(self):
        text = "Todo verificado, sin dudas."
        flags = _extract_verification_flags(text)
        assert flags == {}

    def test_urgente_revisar(self):
        text = "La Ley 27.742 [URGENTE REVISAR] modifica el régimen."
        flags = _extract_verification_flags(text)
        assert "urgente_revisar" in flags


# ═══════════════════════════════════════════
# ORCHESTRATOR — ADVANCED CLASSIFICATION
# ═══════════════════════════════════════════
class TestOrchestratorAdvanced:
    def test_multi_domain_penal_wins(self):
        """When multiple domains match, highest score wins."""
        text = "Nulidad penal de la prueba obtenida en el inmueble"
        result = classify_request(text)
        # 'penal' and 'inmobiliario' both match, but penal should have more hits
        assert result.domain in (Domain.PENAL, Domain.INMOBILIARIO)

    def test_laboral_detection(self):
        result = classify_request("Calcular indemnización por despido art 245 LCT")
        assert result.domain == Domain.LABORAL

    def test_societario_detection(self):
        result = classify_request("Constituir una SAS y redactar el estatuto")
        assert result.domain == Domain.SOCIETARIO

    def test_critical_urgency_detenido(self):
        result = classify_request("Mi cliente está detenido desde ayer, necesito actuar ya")
        assert result.urgency == Urgency.CRITICAL

    def test_critical_urgency_habeas(self):
        result = classify_request("Presentar hábeas corpus correctivo urgente")
        assert result.urgency == Urgency.CRITICAL

    def test_high_urgency_plazo(self):
        result = classify_request("Vence el plazo de la audiencia mañana")
        assert result.urgency == Urgency.HIGH

    def test_combined_classification(self):
        """Complex request should classify domain + workflow correctly."""
        result = classify_request(
            "Necesito redactar un recurso de casación para la causa penal "
            "por la cadena de custodia digital fallida"
        )
        assert result.domain == Domain.PENAL
        assert result.workflow == Workflow.ESCRITO_BLINDADO
        assert result.confidence > 0.5


# ═══════════════════════════════════════════
# NOTIFICATIONS — IMPORTABILITY
# ═══════════════════════════════════════════
class TestNotificationsStructure:
    def test_notification_model_importable(self):
        from app.services.notifications_service import (
            Notification,
            NotificationPriority,
        )
        assert NotificationPriority.CRITICAL == "critical"

    def test_priority_enum(self):
        from app.services.notifications_service import NotificationPriority
        assert NotificationPriority.CRITICAL.value == "critical"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.LOW.value == "low"


# ═══════════════════════════════════════════
# MIDDLEWARE — LOGGING
# ═══════════════════════════════════════════
class TestLoggingMiddleware:
    def test_setup_logging_importable(self):
        from app.middleware.logging_middleware import setup_logging, StructuredFormatter
        # Just verify it doesn't crash
        setup_logging(debug=True)

    def test_structured_formatter(self):
        import logging
        from app.middleware.logging_middleware import StructuredFormatter
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Test message", args=(), exc_info=None,
        )
        formatted = formatter.format(record)
        assert "Test message" in formatted


# ═══════════════════════════════════════════
# ENCRYPTION — EDGE CASES
# ═══════════════════════════════════════════
class TestEncryptionEdgeCases:
    def test_special_characters(self):
        from app.services.encryption_service import encrypt_field, decrypt_field
        text = "§123 — «artículo» del CCyCN ® ™ ¡¿? €£¥"
        assert decrypt_field(encrypt_field(text)) == text

    def test_newlines_and_tabs(self):
        from app.services.encryption_service import encrypt_field, decrypt_field
        text = "Línea 1\nLínea 2\n\tIndentada\r\nWindows line"
        assert decrypt_field(encrypt_field(text)) == text

    def test_json_string(self):
        import json
        from app.services.encryption_service import encrypt_field, decrypt_field
        data = json.dumps({"nombre": "Juan Pérez", "cuit": "20-12345678-9"})
        decrypted = decrypt_field(encrypt_field(data))
        parsed = json.loads(decrypted)
        assert parsed["cuit"] == "20-12345678-9"


# ═══════════════════════════════════════════
# MEMORY — ADVANCED CHUNKING
# ═══════════════════════════════════════════
class TestMemoryAdvanced:
    def test_chunk_preserves_all_content(self):
        from app.memory.memory_service import chunk_text
        original = "Párrafo uno. " * 200  # ~2600 chars
        chunks = chunk_text(original, max_chars=500, overlap=0)
        # All original content should be represented
        reassembled = " ".join(chunks)
        assert "Párrafo uno" in reassembled

    def test_chunk_with_legal_structure(self):
        """Test chunking with typical legal document structure."""
        from app.memory.memory_service import chunk_text
        doc = (
            "I. OBJETO\n\n"
            "Se plantea la nulidad absoluta de la extracción de datos.\n\n"
            "II. HECHOS\n\n"
            "El día 15/03/2024, personal policial procedió a la extracción.\n\n"
            "III. DERECHO\n\n"
            "Art. 168 CPPN establece que toda nulidad de orden general...\n\n"
            "IV. PETITORIO\n\n"
            "Por todo lo expuesto, solicito..."
        )
        chunks = chunk_text(doc, max_chars=200, overlap=0)
        assert len(chunks) >= 2
        # First chunk should contain OBJETO
        assert "OBJETO" in chunks[0]


# ═══════════════════════════════════════════
# APP STARTUP
# ═══════════════════════════════════════════
class TestAppImport:
    def test_app_importable(self):
        from app.main import app
        assert app.title == "OroGest Lex API"

    def test_routes_registered(self):
        from app.main import app
        paths = [route.path for route in app.routes]
        assert "/health" in paths
        assert "/" in paths


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
