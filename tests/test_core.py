"""
OroGest Lex — Tests
Unit tests for core modules: security, orchestrator, audit.
"""

import pytest
from app.core.security import (
    Role,
    Permission,
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    role_has_permission,
    compute_audit_hash,
)
from app.agents.orchestrator import (
    classify_request,
    Domain,
    Urgency,
    Workflow,
    OrchestratorTask,
    TaskState,
)


# ═══════════════════════════════════════════
# SECURITY TESTS
# ═══════════════════════════════════════════
class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "EstudioOro2026!"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrong_password", hashed)

    def test_different_hashes_for_same_password(self):
        p = "TestPassword123"
        h1 = hash_password(p)
        h2 = hash_password(p)
        assert h1 != h2  # bcrypt uses random salt


class TestJWT:
    def test_access_token_roundtrip(self):
        data = {"sub": "test-user-id", "role": "director", "email": "diego@estudiooro.com"}
        token = create_access_token(data)
        decoded = decode_token(token)
        assert decoded["sub"] == "test-user-id"
        assert decoded["role"] == "director"
        assert decoded["type"] == "access"

    def test_refresh_token_roundtrip(self):
        data = {"sub": "test-user-id", "role": "abogado"}
        token = create_refresh_token(data)
        decoded = decode_token(token)
        assert decoded["type"] == "refresh"
        assert "jti" in decoded  # unique ID for refresh tokens


class TestRBAC:
    def test_director_has_all_permissions(self):
        for perm in Permission:
            assert role_has_permission(Role.DIRECTOR, perm)

    def test_abogado_permissions(self):
        assert role_has_permission(Role.ABOGADO, Permission.CASES_READ)
        assert role_has_permission(Role.ABOGADO, Permission.CASES_WRITE)
        assert role_has_permission(Role.ABOGADO, Permission.AI_DRAFT)
        assert not role_has_permission(Role.ABOGADO, Permission.USERS_MANAGE)
        assert not role_has_permission(Role.ABOGADO, Permission.SETTINGS_MANAGE)

    def test_asistente_permissions(self):
        assert role_has_permission(Role.ASISTENTE, Permission.CASES_READ)
        assert role_has_permission(Role.ASISTENTE, Permission.AI_CHAT)
        assert not role_has_permission(Role.ASISTENTE, Permission.CASES_WRITE)
        assert not role_has_permission(Role.ASISTENTE, Permission.AI_DRAFT)
        assert not role_has_permission(Role.ASISTENTE, Permission.CASES_DELETE)

    def test_pasante_permissions(self):
        assert role_has_permission(Role.PASANTE, Permission.CASES_READ)
        assert role_has_permission(Role.PASANTE, Permission.DOCS_READ)
        assert not role_has_permission(Role.PASANTE, Permission.AI_CHAT)
        assert not role_has_permission(Role.PASANTE, Permission.CASES_WRITE)


class TestAuditHash:
    def test_hash_chain_deterministic(self):
        h1 = compute_audit_hash("GENESIS", "event1")
        h2 = compute_audit_hash("GENESIS", "event1")
        assert h1 == h2

    def test_hash_chain_changes_with_input(self):
        h1 = compute_audit_hash("GENESIS", "event1")
        h2 = compute_audit_hash("GENESIS", "event2")
        assert h1 != h2

    def test_hash_chain_integrity(self):
        h1 = compute_audit_hash("GENESIS", "login:diego")
        h2 = compute_audit_hash(h1, "case:create:28979")
        h3 = compute_audit_hash(h2, "ai:query:workflow1")
        # Tampering with h1 should break the chain
        h2_tampered = compute_audit_hash("TAMPERED", "case:create:28979")
        assert h2_tampered != h2
        # All hashes are 64 chars (SHA-256 hex)
        assert all(len(h) == 64 for h in [h1, h2, h3])


# ═══════════════════════════════════════════
# ORCHESTRATOR TESTS
# ═══════════════════════════════════════════
class TestClassifier:
    def test_penal_classification(self):
        result = classify_request("Necesito redactar una nulidad para la causa penal por cadena de custodia")
        assert result.domain == Domain.PENAL
        assert result.workflow == Workflow.ESCRITO_BLINDADO

    def test_inmobiliario_classification(self):
        result = classify_request("Hacé un due diligence del inmueble en Palermo, folio real 123")
        assert result.domain == Domain.INMOBILIARIO
        assert result.workflow == Workflow.DUE_DILIGENCE

    def test_urgency_critical(self):
        result = classify_request("Mi cliente está detenido y necesito un habeas corpus urgente")
        assert result.urgency == Urgency.CRITICAL

    def test_urgency_normal(self):
        result = classify_request("Quiero revisar los estatutos de la SAS")
        assert result.urgency == Urgency.NORMAL

    def test_estrategia_procesal(self):
        result = classify_request("Analizar el riesgo procesal y las chances de la causa")
        assert result.workflow == Workflow.ESTRATEGIA_PROCESAL

    def test_escudo_patrimonial(self):
        result = classify_request("Preparar una propuesta de escudo para un inversor español")
        assert result.workflow == Workflow.ESCUDO_PATRIMONIAL

    def test_general_fallback(self):
        result = classify_request("Buen día, ¿cómo estás?")
        assert result.domain == Domain.GENERAL
        assert result.workflow == Workflow.GENERAL

    def test_confidence_increases_with_matches(self):
        low = classify_request("hola")
        high = classify_request("nulidad penal casación recurso defensa escrito imputado")
        assert high.confidence > low.confidence

    def test_compliance_classification(self):
        result = classify_request("Necesito verificar si el cliente es PEP para el reporte UIF")
        assert result.domain == Domain.COMPLIANCE


class TestOrchestratorTask:
    def test_lifecycle(self):
        task = OrchestratorTask(input_text="Redactar nulidad penal")
        assert task.state == TaskState.PENDING

        task.classify()
        assert task.state == TaskState.CLASSIFIED
        assert task.classification is not None

        task.start()
        assert task.state == TaskState.IN_PROGRESS

        task.complete("Escrito generado correctamente")
        assert task.state == TaskState.COMPLETED
        assert task.result is not None
        assert task.completed_at is not None

    def test_failure_lifecycle(self):
        task = OrchestratorTask(input_text="test")
        task.classify()
        task.start()
        task.fail("Claude API timeout")
        assert task.state == TaskState.FAILED
        assert task.error == "Claude API timeout"

    def test_to_dict(self):
        task = OrchestratorTask(input_text="Nulidad penal por prueba ilegal")
        task.classify()
        d = task.to_dict()
        assert "id" in d
        assert d["state"] == "classified"
        assert d["classification"]["domain"] == "penal"


# ═══════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
