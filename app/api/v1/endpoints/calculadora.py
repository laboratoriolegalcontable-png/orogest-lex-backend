"""
OroGest Lex — Calculadora Laboral
Cálculo de indemnizaciones por despido (Art. 245 LCT) y rubros asociados.

⚠️ ANTI-ALUCINACIÓN: Los valores de RIPTE, SMVM y topes convencionales
cambian periódicamente. Este módulo calcula con los valores que el usuario
provee. NUNCA genera valores de índices por su cuenta.

Rubros calculados:
1. Indemnización por antigüedad (Art. 245 LCT)
2. Preaviso (Art. 231-232 LCT)
3. Integración mes de despido (Art. 233 LCT)
4. SAC proporcional
5. Vacaciones no gozadas (Art. 156 LCT)
6. Art. 2 Ley 25.323 (duplicación por falta de registro)
7. Art. 80 LCT (certificados)
8. Total con y sin intereses
"""

from datetime import date, datetime
from enum import Enum

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.models import User

router = APIRouter(prefix="/calculadora", tags=["calculadora"])


class TipoContrato(str, Enum):
    INDETERMINADO = "indeterminado"
    PLAZO_FIJO = "plazo_fijo"
    EVENTUAL = "eventual"


class CalculoRequest(BaseModel):
    """
    Datos necesarios para el cálculo.
    El usuario DEBE proveer la mejor remuneración mensual normal y habitual.
    """
    # Datos del trabajador
    fecha_ingreso: date
    fecha_egreso: date
    tipo_contrato: TipoContrato = TipoContrato.INDETERMINADO

    # Remuneración (el usuario la provee — NO la inventamos)
    mejor_remuneracion_mensual: float = Field(gt=0, description="Mejor remuneración mensual, normal y habitual (bruta)")

    # Topes (el usuario los provee — son variables según convenio)
    tope_convencional: float | None = Field(None, description="Tope Art. 245: 3x promedio convenio colectivo [VERIFICAR con RIPTE/convenio]")

    # Opcionales para rubros extras
    incluir_sac_proporcional: bool = True
    incluir_vacaciones: bool = True
    incluir_integracion: bool = True
    incluir_art2_ley25323: bool = False  # Duplicación por falta de intimación previa
    incluir_art80: bool = False  # Multa certificados
    dias_vacaciones_correspondientes: int | None = None  # Si no se pone, se calcula por antigüedad

    # Intereses
    tasa_interes_anual: float | None = Field(None, description="Tasa de interés anual para cálculo (ej: 36.0 = 36%)")
    fecha_calculo_intereses: date | None = None


class RubroCalculo(BaseModel):
    concepto: str
    base_calculo: str
    monto: float
    articulo: str
    notas: str | None = None


class CalculoResponse(BaseModel):
    # Datos del cálculo
    antiguedad_anos: int
    antiguedad_meses: int
    mejor_remuneracion: float
    base_indemnizatoria: float  # Con o sin tope
    tope_aplicado: bool
    tope_valor: float | None

    # Rubros
    rubros: list[RubroCalculo]
    subtotal: float

    # Intereses
    intereses: float | None = None
    tasa_aplicada: float | None = None
    dias_intereses: int | None = None

    # Total
    total: float

    # Advertencias anti-alucinación
    advertencias: list[str]


def _calcular_antiguedad(ingreso: date, egreso: date) -> tuple[int, int]:
    """Calcula antigüedad en años y meses completos."""
    anos = egreso.year - ingreso.year
    meses = egreso.month - ingreso.month
    if egreso.day < ingreso.day:
        meses -= 1
    if meses < 0:
        anos -= 1
        meses += 12
    return max(0, anos), max(0, meses)


def _dias_vacaciones_por_antiguedad(anos: int) -> int:
    """Art. 150 LCT: días de vacaciones según antigüedad."""
    if anos < 5:
        return 14
    elif anos < 10:
        return 21
    elif anos < 20:
        return 28
    else:
        return 35


@router.post("/indemnizacion", response_model=CalculoResponse)
async def calcular_indemnizacion(
    body: CalculoRequest,
    user: User = Depends(get_current_user),
):
    """
    Calcula indemnización por despido sin justa causa.

    ⚠️ Los valores de topes, RIPTE y convenios NO son generados por el sistema.
    El usuario debe verificarlos con fuentes oficiales.
    """
    advertencias = []
    rubros: list[RubroCalculo] = []

    # ── Antigüedad ──
    anos, meses = _calcular_antiguedad(body.fecha_ingreso, body.fecha_egreso)
    antiguedad_total_meses = anos * 12 + meses

    if antiguedad_total_meses < 3:
        advertencias.append(
            "Antigüedad menor a 3 meses: verificar si corresponde período de prueba (Art. 92 bis LCT)"
        )

    # ── Base indemnizatoria ──
    base = body.mejor_remuneracion_mensual
    tope_aplicado = False

    if body.tope_convencional and body.tope_convencional > 0:
        if base > body.tope_convencional:
            base = body.tope_convencional
            tope_aplicado = True
            advertencias.append(
                f"Se aplicó tope convencional Art. 245: ${body.tope_convencional:,.2f}. "
                "[VERIFICAR tope vigente con RIPTE y convenio colectivo aplicable]"
            )
        # Piso Vizzoti (67% de la mejor remuneración)
        piso_vizzoti = body.mejor_remuneracion_mensual * 0.67
        if base < piso_vizzoti:
            base = piso_vizzoti
            advertencias.append(
                f"Se aplicó piso Vizzoti (67%): ${piso_vizzoti:,.2f}. "
                "CSJN 'Vizzoti c/ AMSA' (2004) [VERIFICAR vigencia]"
            )
    else:
        advertencias.append(
            "No se proporcionó tope convencional. El cálculo usa la mejor remuneración sin tope. "
            "[VERIFICAR: obtener tope del convenio colectivo aplicable]"
        )

    # ── 1. Indemnización por antigüedad (Art. 245) ──
    periodos = max(1, anos)  # Mínimo 1 sueldo
    if meses > 3:
        periodos = anos + 1  # Fracción mayor a 3 meses = período completo (jurisprudencia)

    monto_245 = base * periodos
    rubros.append(RubroCalculo(
        concepto="Indemnización por antigüedad",
        base_calculo=f"${base:,.2f} x {periodos} períodos",
        monto=round(monto_245, 2),
        articulo="Art. 245 LCT",
        notas=f"Antigüedad: {anos} años, {meses} meses"
    ))

    # ── 2. Preaviso (Art. 231-232) ──
    if anos < 5:
        meses_preaviso = 1
    else:
        meses_preaviso = 2

    monto_preaviso = body.mejor_remuneracion_mensual * meses_preaviso
    rubros.append(RubroCalculo(
        concepto="Indemnización sustitutiva de preaviso",
        base_calculo=f"${body.mejor_remuneracion_mensual:,.2f} x {meses_preaviso} mes(es)",
        monto=round(monto_preaviso, 2),
        articulo="Art. 232 LCT",
    ))

    # SAC sobre preaviso
    sac_preaviso = monto_preaviso / 12
    rubros.append(RubroCalculo(
        concepto="SAC sobre preaviso",
        base_calculo=f"${monto_preaviso:,.2f} / 12",
        monto=round(sac_preaviso, 2),
        articulo="Art. 121 LCT",
    ))

    # ── 3. Integración mes de despido (Art. 233) ──
    if body.incluir_integracion:
        dias_restantes = 30 - body.fecha_egreso.day
        if dias_restantes > 0:
            valor_dia = body.mejor_remuneracion_mensual / 30
            monto_integracion = valor_dia * dias_restantes
            rubros.append(RubroCalculo(
                concepto="Integración mes de despido",
                base_calculo=f"${valor_dia:,.2f}/día x {dias_restantes} días",
                monto=round(monto_integracion, 2),
                articulo="Art. 233 LCT",
            ))
            # SAC sobre integración
            sac_integ = monto_integracion / 12
            rubros.append(RubroCalculo(
                concepto="SAC sobre integración",
                base_calculo=f"${monto_integracion:,.2f} / 12",
                monto=round(sac_integ, 2),
                articulo="Art. 121 LCT",
            ))

    # ── 4. SAC proporcional ──
    if body.incluir_sac_proporcional:
        dias_semestre = body.fecha_egreso.day
        if body.fecha_egreso.month <= 6:
            dias_semestre = (body.fecha_egreso - date(body.fecha_egreso.year, 1, 1)).days
        else:
            dias_semestre = (body.fecha_egreso - date(body.fecha_egreso.year, 7, 1)).days

        sac_prop = body.mejor_remuneracion_mensual / 2 * dias_semestre / 182.5
        rubros.append(RubroCalculo(
            concepto="SAC proporcional",
            base_calculo=f"(${body.mejor_remuneracion_mensual:,.2f}/2) x {dias_semestre}/182.5 días",
            monto=round(max(0, sac_prop), 2),
            articulo="Art. 123 LCT",
        ))

    # ── 5. Vacaciones no gozadas ──
    if body.incluir_vacaciones:
        dias_vac = body.dias_vacaciones_correspondientes or _dias_vacaciones_por_antiguedad(anos)
        # Proporcional al tiempo trabajado en el año
        dias_trabajados_ano = (body.fecha_egreso - date(body.fecha_egreso.year, 1, 1)).days
        dias_vac_prop = dias_vac * dias_trabajados_ano / 365
        valor_dia_vac = body.mejor_remuneracion_mensual / 25  # Art. 155 LCT: /25
        monto_vac = valor_dia_vac * dias_vac_prop

        rubros.append(RubroCalculo(
            concepto="Vacaciones no gozadas (proporcional)",
            base_calculo=f"${valor_dia_vac:,.2f}/día x {dias_vac_prop:.1f} días",
            monto=round(max(0, monto_vac), 2),
            articulo="Art. 156 LCT",
            notas=f"Base: {dias_vac} días por antigüedad, proporcional a {dias_trabajados_ano} días trabajados",
        ))

    # ── 6. Art. 2 Ley 25.323 ──
    if body.incluir_art2_ley25323:
        monto_art2 = monto_245 * 0.5
        rubros.append(RubroCalculo(
            concepto="Incremento Art. 2 Ley 25.323",
            base_calculo=f"50% de indemnización Art. 245 (${monto_245:,.2f})",
            monto=round(monto_art2, 2),
            articulo="Art. 2 Ley 25.323",
            notas="Requiere intimación fehaciente previa sin resultado en plazo legal",
        ))

    # ── 7. Art. 80 LCT ──
    if body.incluir_art80:
        monto_art80 = body.mejor_remuneracion_mensual * 3
        rubros.append(RubroCalculo(
            concepto="Multa por certificados (Art. 80 LCT)",
            base_calculo=f"3 x mejor remuneración (${body.mejor_remuneracion_mensual:,.2f})",
            monto=round(monto_art80, 2),
            articulo="Art. 80 LCT / Art. 45 Ley 25.345",
            notas="Requiere intimación previa de 30 días hábiles tras extinción",
        ))

    # ── Subtotal ──
    subtotal = round(sum(r.monto for r in rubros), 2)

    # ── Intereses ──
    intereses = None
    dias_intereses = None
    if body.tasa_interes_anual and body.fecha_calculo_intereses:
        dias_intereses = (body.fecha_calculo_intereses - body.fecha_egreso).days
        if dias_intereses > 0:
            tasa_diaria = body.tasa_interes_anual / 100 / 365
            intereses = round(subtotal * tasa_diaria * dias_intereses, 2)

    total = round(subtotal + (intereses or 0), 2)

    # ── Advertencias generales ──
    advertencias.extend([
        "[VERIFICAR] Los montos de SMVM, RIPTE y topes convencionales cambian periódicamente. "
        "Consultar fuentes oficiales del Ministerio de Trabajo.",
        "[VERIFICAR] Este cálculo es orientativo. La liquidación definitiva debe contemplar "
        "el convenio colectivo aplicable y la jurisprudencia del fuero.",
    ])

    return CalculoResponse(
        antiguedad_anos=anos,
        antiguedad_meses=meses,
        mejor_remuneracion=body.mejor_remuneracion_mensual,
        base_indemnizatoria=round(base, 2),
        tope_aplicado=tope_aplicado,
        tope_valor=body.tope_convencional,
        rubros=rubros,
        subtotal=subtotal,
        intereses=intereses,
        tasa_aplicada=body.tasa_interes_anual,
        dias_intereses=dias_intereses,
        total=total,
        advertencias=advertencias,
    )
