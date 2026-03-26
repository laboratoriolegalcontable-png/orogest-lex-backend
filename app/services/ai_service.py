"""
OroGest Lex — AI Service v2 (Fase 16)
Enhanced Claude proxy with RAG context injection from memory.

Flow:
1. Search memory for relevant context
2. Build system prompt: base + workflow + case context + RAG context
3. Call Claude API
4. Extract anti-hallucination flags
5. Store conversation + new memory chunks
"""

import re
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.models import AIConversation

settings = get_settings()

ORACULO_SYSTEM_PROMPT = """Sos el asistente legal de Estudio Oro S.A.S. (CUIT 30-71933033-5), 
dirigido por el Dr. Diego Orosa (Abogado Penalista CPACF T° 145 F° 433 | Corredor Inmobiliario CASI T° LV F° 206).

REGLAS ANTI-ALUCINACIÓN OBLIGATORIAS:
1. NUNCA inventar números de causa, CUIT, matrículas ni datos de personas reales.
2. NUNCA inventar valores de índices (ICL, RIPTE, UVA, UMA, CER). Indicar [VERIFICAR VALOR ACTUAL].
3. NUNCA inventar texto de artículos legales. Parafrasear y marcar [VERIFICAR TEXTO].
4. Cuando cites jurisprudencia, marcar [VERIFICAR CITA] salvo que el usuario la haya proporcionado.
5. Distinguir siempre entre lo que sabés con certeza y lo que inferís.
6. Usar etiquetas: [VERIFICAR], [INFERIDO], [FUENTE REQUERIDA], [URGENTE REVISAR].

FIRMA PARA ESCRITOS:
Dr. Diego Orosa
Abogado — CPACF T° 145 F° 433
Estudio Oro S.A.S.
"""

WORKFLOW_PROMPTS: dict[str, str] = {
    "escrito_blindado": "\nMODO: Escrito Blindado Casación-Ready.\nEstructura: 1) Encabezado (Tribunal/Causa/Carátula) 2) Objeto 3) Hechos procesalmente relevantes\n4) Derecho (normas + jurisprudencia con [VERIFICAR]) 5) Petitorio concreto 6) Firma.\nAplicar triple agente: redactor → crítico → blindador.\n",
    "due_diligence": "\nMODO: Due Diligence Inmobiliario.\nGenerar checklist por jurisdicción (ARG/ESP/URY).\nSemáforo: 🟢 sin riesgo / 🟡 revisar / 🔴 no operar.\n",
    "estrategia_procesal": "\nMODO: Estrategia Procesal con Scoring.\nFactores: solidez probatoria fiscal (25%), cadena custodia digital (20%),\njurisprudencia favorable (20%), nulidades (15%), perfil tribunal (10%), antecedentes (10%).\nOutput: score 0-100, semáforo, top 3 planteos, ruta casación.\n",
    "escudo_patrimonial": "\nMODO: Propuesta Escudo Patrimonial.\n3 tiers: Básico (diagnóstico), Plus (due diligence + societario), Premium (integral ARG/ESP/URY).\n",
}


def _extract_verification_flags(text: str) -> dict:
    flags = {
        "verificar": re.findall(r"\[VERIFICAR[^\]]*\]", text),
        "inferido": re.findall(r"\[INFERIDO[^\]]*\]", text),
        "fuente_requerida": re.findall(r"\[FUENTE REQUERIDA[^\]]*\]", text),
        "urgente_revisar": re.findall(r"\[URGENTE REVISAR[^\]]*\]", text),
    }
    return {k: v for k, v in flags.items() if v}


def _build_system_prompt(
    workflow: str | None = None,
    rag_context: str | None = None,
    system_prompt_override: str | None = None,
    case_info: dict | None = None,
) -> str:
    parts = [system_prompt_override or ORACULO_SYSTEM_PROMPT]

    if workflow and workflow in WORKFLOW_PROMPTS:
        parts.append(WORKFLOW_PROMPTS[workflow])

    if case_info:
        ctx = "\n--- CONTEXTO DE LA CAUSA ACTIVA ---\n"
        for key in ("caption", "branch", "jurisdiction", "court", "case_number"):
            ctx += f"{key.replace('_',' ').title()}: {case_info.get(key, 'N/D')}\n"
        if case_info.get("notes"):
            ctx += f"Notas: {case_info['notes'][:500]}\n"
        parts.append(ctx)

    if rag_context:
        parts.append(
            "\n--- CONTEXTO RECUPERADO DE MEMORIA (referencia, NO fuente citada) ---\n"
            + rag_context
            + "\n--- FIN CONTEXTO ---\n"
        )

    return "\n".join(parts)


async def query_claude(
    message: str,
    conversation_history: list[dict] | None = None,
    workflow: str | None = None,
    system_prompt_override: str | None = None,
    rag_context: str | None = None,
    case_info: dict | None = None,
) -> dict:
    system = _build_system_prompt(workflow, rag_context, system_prompt_override, case_info)

    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": message})

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.CLAUDE_MODEL,
                "max_tokens": settings.CLAUDE_MAX_TOKENS,
                "system": system,
                "messages": messages,
            },
        )
        response.raise_for_status()
        data = response.json()

    response_text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            response_text += block.get("text", "")

    usage = data.get("usage", {})
    tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

    return {
        "response": response_text,
        "tokens_used": tokens,
        "verification_flags": _extract_verification_flags(response_text) or None,
        "model": data.get("model", settings.CLAUDE_MODEL),
    }


async def create_or_continue_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    message: str,
    case_id: uuid.UUID | None = None,
    workflow: str | None = None,
    conversation_id: uuid.UUID | None = None,
    system_prompt_override: str | None = None,
) -> tuple[dict, AIConversation]:
    conversation: AIConversation | None = None

    if conversation_id:
        conversation = await db.get(AIConversation, conversation_id)
        if conversation and conversation.user_id != user_id:
            raise PermissionError("No tenés acceso a esta conversación")

    history = conversation.messages if conversation else []

    # ── RAG context + case info ──
    rag_context = None
    case_info = None
    try:
        from app.memory.memory_service import get_context_for_query
        branch = None
        if case_id:
            from app.models.models import Case
            case = await db.get(Case, case_id)
            if case:
                branch = case.branch
                case_info = {
                    "caption": case.caption, "branch": case.branch,
                    "jurisdiction": case.jurisdiction, "court": case.court,
                    "case_number": case.case_number, "notes": case.notes,
                }
        rag_context = await get_context_for_query(
            db, message, case_id=str(case_id) if case_id else None, branch=branch
        )
    except Exception:
        pass

    result = await query_claude(
        message=message,
        conversation_history=history,
        workflow=workflow,
        system_prompt_override=system_prompt_override,
        rag_context=rag_context if rag_context else None,
        case_info=case_info,
    )

    now = datetime.now(timezone.utc).isoformat()
    new_messages = history + [
        {"role": "user", "content": message, "timestamp": now},
        {"role": "assistant", "content": result["response"], "timestamp": now},
    ]
    flags_count = len(sum(result["verification_flags"].values(), [])) if result["verification_flags"] else 0

    if conversation:
        conversation.messages = new_messages
        conversation.tokens_used += result["tokens_used"]
        conversation.verification_flags_count += flags_count
    else:
        conversation = AIConversation(
            user_id=user_id, case_id=case_id, workflow=workflow,
            messages=new_messages, tokens_used=result["tokens_used"],
            model_used=result["model"], verification_flags_count=flags_count,
        )
        db.add(conversation)

    await db.flush()

    # Store response in memory for future RAG
    if result["response"] and len(result["response"]) > 100:
        try:
            from app.memory.memory_service import store_memory
            await store_memory(
                db=db, content=result["response"],
                source_type="conversation", source_id=str(conversation.id),
                branch=workflow, user_id=user_id, tags=workflow,
            )
        except Exception:
            pass

    return result, conversation
