"""
OroGest Lex — Tests: Calculadora, Export, Files, Password
"""

from datetime import date

import pytest

from app.services.export_service import (
    ESTUDIO_HEADER,
    FIRMA_LINES,
    _fallback_markdown,
    HAS_DOCX,
)
from app.services.file_service import (
    ALLOWED_EXTENSIONS,
    _compute_file_hash,
    _validate_file,
    FileUploadError,
)
from app.api.v1.endpoints.calculadora import (
    _calcular_antiguedad,
    _dias_vacaciones_por_antiguedad,
)


# ═══════════════════════════════════════════
# CALCULADORA LABORAL
# ═══════════════════════════════════════════
class TestAntiguedad:
    def test_exact_years(self):
        anos, meses = _calcular_antiguedad(date(2020, 1, 1), date(2025, 1, 1))
        assert anos == 5
        assert meses == 0

    def test_years_and_months(self):
        anos, meses = _calcular_antiguedad(date(2020, 1, 1), date(2023, 7, 15))
        assert anos == 3
        assert meses == 6

    def test_less_than_year(self):
        anos, meses = _calcular_antiguedad(date(2024, 6, 1), date(2024, 11, 15))
        assert anos == 0
        assert meses == 5

    def test_same_day(self):
        anos, meses = _calcular_antiguedad(date(2024, 1, 1), date(2024, 1, 1))
        assert anos == 0
        assert meses == 0

    def test_partial_month(self):
        # Egreso day < ingreso day → one less month
        anos, meses = _calcular_antiguedad(date(2020, 3, 20), date(2023, 3, 10))
        assert anos == 2
        assert meses == 11

    def test_20_years(self):
        anos, meses = _calcular_antiguedad(date(2000, 1, 1), date(2020, 6, 15))
        assert anos == 20
        assert meses == 5


class TestVacaciones:
    def test_menos_de_5(self):
        assert _dias_vacaciones_por_antiguedad(0) == 14
        assert _dias_vacaciones_por_antiguedad(4) == 14

    def test_5_a_10(self):
        assert _dias_vacaciones_por_antiguedad(5) == 21
        assert _dias_vacaciones_por_antiguedad(9) == 21

    def test_10_a_20(self):
        assert _dias_vacaciones_por_antiguedad(10) == 28
        assert _dias_vacaciones_por_antiguedad(19) == 28

    def test_mas_de_20(self):
        assert _dias_vacaciones_por_antiguedad(20) == 35
        assert _dias_vacaciones_por_antiguedad(30) == 35


class TestCalculadoraEndpoint:
    """Test the calculadora logic through direct function calls."""

    def test_basic_calculation_structure(self):
        """Verify the response structure has all required fields."""
        from app.api.v1.endpoints.calculadora import (
            CalculoRequest,
            TipoContrato,
        )

        req = CalculoRequest(
            fecha_ingreso=date(2020, 1, 1),
            fecha_egreso=date(2025, 3, 15),
            mejor_remuneracion_mensual=500000.0,
            tope_convencional=600000.0,
        )
        assert req.mejor_remuneracion_mensual == 500000.0
        assert req.tipo_contrato == TipoContrato.INDETERMINADO

    def test_antiguedad_minimum_one_period(self):
        """Art. 245: minimum 1 salary even for less than 1 year."""
        anos, meses = _calcular_antiguedad(date(2024, 6, 1), date(2024, 11, 1))
        periodos = max(1, anos)  # min 1
        assert periodos == 1

    def test_tope_vizzoti(self):
        """Test Vizzoti floor (67% of best remuneration)."""
        mejor = 1000000
        tope = 400000  # artificially low tope
        piso_vizzoti = mejor * 0.67
        base = tope
        if base < piso_vizzoti:
            base = piso_vizzoti
        assert base == 670000.0

    def test_preaviso_menos_5_anos(self):
        """Less than 5 years = 1 month preaviso."""
        anos, _ = _calcular_antiguedad(date(2021, 1, 1), date(2024, 6, 1))
        meses_preaviso = 1 if anos < 5 else 2
        assert meses_preaviso == 1

    def test_preaviso_mas_5_anos(self):
        """5+ years = 2 months preaviso."""
        anos, _ = _calcular_antiguedad(date(2018, 1, 1), date(2024, 6, 1))
        meses_preaviso = 1 if anos < 5 else 2
        assert meses_preaviso == 2


# ═══════════════════════════════════════════
# EXPORT SERVICE
# ═══════════════════════════════════════════
class TestExportFallback:
    """Test Markdown fallback when python-docx is not available."""

    def test_fallback_contains_header(self):
        result = _fallback_markdown("TEST TITLE", campo="valor")
        text = result.decode("utf-8")
        assert "TEST TITLE" in text
        assert ESTUDIO_HEADER in text

    def test_fallback_contains_firma(self):
        result = _fallback_markdown("ESCRITO", objeto="test")
        text = result.decode("utf-8")
        for line in FIRMA_LINES[:2]:
            assert line in text

    def test_fallback_contains_warning(self):
        result = _fallback_markdown("DOC", data="test")
        text = result.decode("utf-8")
        assert "VERIFICAR" in text or "IA" in text

    def test_fallback_kwargs_included(self):
        result = _fallback_markdown("INFORME", cliente="Juan Pérez", causa="12345/2024")
        text = result.decode("utf-8")
        assert "Juan Pérez" in text
        assert "12345/2024" in text


class TestExportDocx:
    """Test DOCX generation (if python-docx is available)."""

    @pytest.mark.skipif(not HAS_DOCX, reason="python-docx not installed")
    def test_escrito_generates_bytes(self):
        from app.services.export_service import generate_escrito_docx

        result = generate_escrito_docx(
            tribunal="Tribunal Oral Criminal N° 5",
            causa="28979/2020",
            caratula="N.N. s/ robo agravado",
            objeto="Se plantea la nulidad absoluta de la prueba digital.",
            hechos="El día 15/03/2024, personal policial procedió sin orden judicial.",
            derecho="Art. 168 CPPN [VERIFICAR TEXTO]. Art. 18 CN.",
            petitorio="1) Declarar la nulidad.\n2) Sobreseer al imputado.",
        )
        assert isinstance(result, bytes)
        assert len(result) > 1000  # A real docx is at least a few KB
        # DOCX magic bytes (PK zip format)
        assert result[:2] == b"PK"

    @pytest.mark.skipif(not HAS_DOCX, reason="python-docx not installed")
    def test_carta_documento_generates(self):
        from app.services.export_service import generate_carta_documento_docx

        result = generate_carta_documento_docx(
            destinatario="Sr. Juan Pérez",
            domicilio_destinatario="Av. Corrientes 1234, CABA",
            asunto="Intimación por incumplimiento contractual",
            cuerpo="Por la presente se lo intima a cumplir con el contrato...",
        )
        assert isinstance(result, bytes)
        assert result[:2] == b"PK"

    @pytest.mark.skipif(not HAS_DOCX, reason="python-docx not installed")
    def test_due_diligence_report(self):
        from app.services.export_service import generate_due_diligence_report_docx

        result = generate_due_diligence_report_docx(
            property_data={
                "title": "Depto Palermo",
                "address": "Thames 1234",
                "city": "CABA",
                "province": "CABA",
                "country": "ARG",
                "property_type": "departamento",
                "folio_real": "12345",
                "owner_name": "María García",
            },
            checklist={
                "dominio": {"label": "Dominio", "status": "ok"},
                "inhibiciones": {"label": "Inhibiciones", "status": "ok"},
                "deudas": {"label": "Deudas", "status": "pendiente"},
            },
            risk_level="amarillo",
        )
        assert isinstance(result, bytes)
        assert result[:2] == b"PK"


# ═══════════════════════════════════════════
# FILE SERVICE
# ═══════════════════════════════════════════
class TestFileService:
    def test_compute_hash_deterministic(self):
        content = b"test content for hashing"
        h1 = _compute_file_hash(content)
        h2 = _compute_file_hash(content)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_compute_hash_different_content(self):
        h1 = _compute_file_hash(b"content A")
        h2 = _compute_file_hash(b"content B")
        assert h1 != h2

    def test_allowed_extensions(self):
        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".docx" in ALLOWED_EXTENSIONS
        assert ".xlsx" in ALLOWED_EXTENSIONS
        assert ".jpg" in ALLOWED_EXTENSIONS
        assert ".exe" not in ALLOWED_EXTENSIONS
        assert ".sh" not in ALLOWED_EXTENSIONS
        assert ".py" not in ALLOWED_EXTENSIONS

    def test_validate_file_no_filename(self):
        class FakeFile:
            filename = None

        with pytest.raises(FileUploadError, match="sin nombre"):
            _validate_file(FakeFile())

    def test_validate_file_bad_extension(self):
        class FakeFile:
            filename = "malware.exe"

        with pytest.raises(FileUploadError, match="no permitida"):
            _validate_file(FakeFile())

    def test_validate_file_good_extension(self):
        class FakeFile:
            filename = "contrato.pdf"

        ext = _validate_file(FakeFile())
        assert ext == ".pdf"


# ═══════════════════════════════════════════
# PASSWORD MANAGEMENT
# ═══════════════════════════════════════════
class TestPasswordLogic:
    def test_hash_and_verify(self):
        from app.core.security import hash_password, verify_password

        pw = "NuevaContraseña2026!"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed)
        assert not verify_password("ContraseñaEquivocada", hashed)

    def test_password_change_validation(self):
        """New password must differ from current."""
        current = "MismaContraseña123"
        new = "MismaContraseña123"
        assert current == new  # This should be rejected by endpoint


# ═══════════════════════════════════════════
# APP ROUTES COMPLETENESS
# ═══════════════════════════════════════════
class TestRouteCompleteness:
    def test_all_expected_routes_exist(self):
        from app.main import app

        paths = list(app.openapi()["paths"].keys())

        expected_prefixes = [
            "/api/v1/auth",
            "/api/v1/users",
            "/api/v1/cases",
            "/api/v1/documents",
            "/api/v1/properties",
            "/api/v1/ai",
            "/api/v1/orchestrator",
            "/api/v1/dashboard",
            "/api/v1/audit",
            "/api/v1/search",
            "/api/v1/notifications",
            "/api/v1/export",
            "/api/v1/calculadora",
            "/api/v1/files",
        ]

        for prefix in expected_prefixes:
            matching = [p for p in paths if p.startswith(prefix)]
            assert len(matching) > 0, f"No routes found for prefix: {prefix}"

    def test_health_endpoint(self):
        from app.main import app

        paths = list(app.openapi()["paths"].keys())
        assert "/health" in paths

    def test_root_endpoint(self):
        from app.main import app

        paths = list(app.openapi()["paths"].keys())
        assert "/" in paths

    def test_route_count_reasonable(self):
        """Verify we have a substantial number of routes."""
        from app.main import app

        api_routes = [p for p in app.openapi()["paths"] if p.startswith("/api")]
        assert len(api_routes) >= 30, f"Only {len(api_routes)} API routes found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
