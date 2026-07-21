"""
OroGest Lex — Tests: Clients, Templates, Timeline, Batch
"""

import re
import uuid

import pytest


# ═══════════════════════════════════════════
# CLIENT MODEL
# ═══════════════════════════════════════════
class TestClientModel:
    def test_client_importable(self):
        from app.models.models import Client, CaseClient

        assert Client.__tablename__ == "clients"
        assert CaseClient.__tablename__ == "case_clients"

    def test_client_schema(self):
        from app.api.v1.endpoints.clients import ClientCreate

        client = ClientCreate(
            full_name="Juan Pérez",
            document_type="DNI",
            document_number="30123456",
            email="juan@example.com",
            phone="+54 11 1234-5678",
            client_type="persona_fisica",
            client_category="imputado",
            is_pep=False,
        )
        assert client.full_name == "Juan Pérez"
        assert client.is_pep is False

    def test_client_pep_tracking(self):
        from app.api.v1.endpoints.clients import ClientCreate

        pep_client = ClientCreate(
            full_name="Funcionario X",
            document_type="CUIT",
            document_number="20-12345678-9",
            is_pep=True,
            client_type="persona_fisica",
        )
        assert pep_client.is_pep is True

    def test_link_request_schema(self):
        from app.api.v1.endpoints.clients import LinkClientRequest

        link = LinkClientRequest(
            client_id=uuid.uuid4(),
            case_id=uuid.uuid4(),
            role="imputado",
            is_primary=True,
        )
        assert link.role == "imputado"


# ═══════════════════════════════════════════
# WRITING TEMPLATES
# ═══════════════════════════════════════════
class TestWritingTemplates:
    def test_template_model_importable(self):
        from app.models.models import WritingTemplate

        assert WritingTemplate.__tablename__ == "writing_templates"

    def test_system_templates_exist(self):
        from app.api.v1.endpoints.templates import SYSTEM_TEMPLATES

        assert len(SYSTEM_TEMPLATES) >= 3

        # Check required fields
        for tpl in SYSTEM_TEMPLATES:
            assert "name" in tpl
            assert "branch" in tpl
            assert "doc_type" in tpl
            assert "template_content" in tpl
            assert "variables_schema" in tpl
            assert len(tpl["template_content"]) > 100

    def test_nulidad_template_has_placeholders(self):
        from app.api.v1.endpoints.templates import SYSTEM_TEMPLATES

        nulidad = next(t for t in SYSTEM_TEMPLATES if "nulidad" in t["name"].lower())
        content = nulidad["template_content"]

        # Should have {{variable}} placeholders
        placeholders = re.findall(r"\{\{(\w+)\}\}", content)
        assert len(placeholders) >= 5
        assert "tribunal" in placeholders
        assert "cliente" in placeholders
        assert "numero_causa" in placeholders

    def test_template_rendering_logic(self):
        """Test placeholder replacement logic."""
        template = "Señor Juez del {{tribunal}}: En la causa {{causa}} de {{cliente}}."
        variables = {"tribunal": "TOC N° 5", "causa": "28979/2020", "cliente": "Juan Pérez"}

        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)

        assert "TOC N° 5" in rendered
        assert "28979/2020" in rendered
        assert "Juan Pérez" in rendered
        assert "{{" not in rendered

    def test_unfilled_detection(self):
        """Test detection of unfilled variables."""
        rendered = "Tribunal: TOC N° 5. Cliente: {{cliente}}. Causa: {{causa}}."
        unfilled = re.findall(r"\{\{(\w+)\}\}", rendered)
        assert "cliente" in unfilled
        assert "causa" in unfilled
        assert len(unfilled) == 2

    def test_morigeration_template(self):
        from app.api.v1.endpoints.templates import SYSTEM_TEMPLATES

        morig = next(t for t in SYSTEM_TEMPLATES if "morigeración" in t["name"].lower())
        assert "24.660" in morig["template_content"]
        assert "DOMICILIARIO" in morig["template_content"]

    def test_carta_documento_template(self):
        from app.api.v1.endpoints.templates import SYSTEM_TEMPLATES

        carta = next(t for t in SYSTEM_TEMPLATES if "carta documento" in t["name"].lower())
        assert "48" in carta["template_content"]  # 48 hours
        assert "fehacientemente" in carta["template_content"]


# ═══════════════════════════════════════════
# TIMELINE
# ═══════════════════════════════════════════
class TestTimeline:
    def test_action_labels_complete(self):
        from app.api.v1.endpoints.timeline import ACTION_LABELS

        assert "case.create" in ACTION_LABELS
        assert "document.create" in ACTION_LABELS
        assert "ai.query" in ACTION_LABELS
        assert "ai.draft" in ACTION_LABELS
        assert "export.escrito" in ACTION_LABELS

    def test_action_labels_are_spanish(self):
        from app.api.v1.endpoints.timeline import ACTION_LABELS

        for key, label in ACTION_LABELS.items():
            # Labels should be in Spanish
            assert len(label) > 5, f"Label too short for {key}: {label}"


# ═══════════════════════════════════════════
# BATCH OPERATIONS
# ═══════════════════════════════════════════
class TestBatchOperations:
    def test_batch_status_schema(self):
        from app.api.v1.endpoints.batch import BatchStatusUpdate

        batch = BatchStatusUpdate(
            case_ids=[uuid.uuid4(), uuid.uuid4(), uuid.uuid4()],
            new_status="archivada",
        )
        assert len(batch.case_ids) == 3
        assert batch.new_status == "archivada"

    def test_batch_assign_schema(self):
        from app.api.v1.endpoints.batch import BatchAssign

        batch = BatchAssign(
            case_ids=[uuid.uuid4()],
            assign_to=uuid.uuid4(),
        )
        assert len(batch.case_ids) == 1

    def test_batch_tag_schema(self):
        from app.api.v1.endpoints.batch import BatchTagRequest

        batch = BatchTagRequest(
            case_ids=[uuid.uuid4(), uuid.uuid4()],
            tag_key="prioridad",
            tag_value="alta",
        )
        assert batch.tag_key == "prioridad"

    def test_batch_max_50(self):
        """Batch operations should limit to 50 items."""
        from app.api.v1.endpoints.batch import BatchStatusUpdate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BatchStatusUpdate(
                case_ids=[uuid.uuid4() for _ in range(51)],
                new_status="archivada",
            )

    def test_batch_min_1(self):
        from app.api.v1.endpoints.batch import BatchStatusUpdate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BatchStatusUpdate(case_ids=[], new_status="archivada")


# ═══════════════════════════════════════════
# CLI STRUCTURE
# ═══════════════════════════════════════════
class TestCLI:
    def test_cli_importable(self):
        from scripts.cli import main, cmd_stats, cmd_verify_audit

        assert callable(main)
        assert callable(cmd_stats)
        assert callable(cmd_verify_audit)


# ═══════════════════════════════════════════
# ROUTE COMPLETENESS v2
# ═══════════════════════════════════════════
class TestRouteCompletenessV2:
    def test_all_new_routes_exist(self):
        from app.main import app

        paths = list(app.openapi()["paths"].keys())

        new_prefixes = [
            "/api/v1/clients",
            "/api/v1/templates",
            "/api/v1/timeline",
            "/api/v1/batch",
        ]
        for prefix in new_prefixes:
            matching = [p for p in paths if p.startswith(prefix)]
            assert len(matching) > 0, f"No routes for: {prefix}"

    def test_total_routes_over_60(self):
        from app.main import app

        api_routes = [p for p in app.openapi()["paths"] if p.startswith("/api")]
        assert len(api_routes) >= 60, f"Only {len(api_routes)} API routes"

    def test_client_crud_routes(self):
        from app.main import app

        paths = list(app.openapi()["paths"].keys())
        assert "/api/v1/clients/" in paths
        assert "/api/v1/clients/{client_id}" in paths
        assert "/api/v1/clients/link-case" in paths
        assert "/api/v1/clients/{client_id}/cases" in paths

    def test_template_routes(self):
        from app.main import app

        paths = list(app.openapi()["paths"].keys())
        assert "/api/v1/templates/" in paths
        assert "/api/v1/templates/{template_id}" in paths
        assert "/api/v1/templates/{template_id}/render" in paths
        assert "/api/v1/templates/seed-system" in paths

    def test_batch_routes(self):
        from app.main import app

        paths = list(app.openapi()["paths"].keys())
        assert "/api/v1/batch/cases/update-status" in paths
        assert "/api/v1/batch/cases/assign" in paths
        assert "/api/v1/batch/cases/tag" in paths


# ═══════════════════════════════════════════
# MODEL COMPLETENESS
# ═══════════════════════════════════════════
class TestModelCompleteness:
    def test_all_models_importable(self):
        from app.models.models import (
            User,
            Case,
            Document,
            Property,
            AIConversation,
            AuditLog,
            Client,
            CaseClient,
            WritingTemplate,
        )

        # 9 main models
        tables = [
            User.__tablename__,
            Case.__tablename__,
            Document.__tablename__,
            Property.__tablename__,
            AIConversation.__tablename__,
            AuditLog.__tablename__,
            Client.__tablename__,
            CaseClient.__tablename__,
            WritingTemplate.__tablename__,
        ]
        assert len(set(tables)) == 9

    def test_case_client_many_to_many(self):
        from app.models.models import CaseClient

        assert hasattr(CaseClient, "case_id")
        assert hasattr(CaseClient, "client_id")
        assert hasattr(CaseClient, "role")

    def test_writing_template_fields(self):
        from app.models.models import WritingTemplate

        assert hasattr(WritingTemplate, "template_content")
        assert hasattr(WritingTemplate, "variables_schema")
        assert hasattr(WritingTemplate, "usage_count")
        assert hasattr(WritingTemplate, "is_system")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
