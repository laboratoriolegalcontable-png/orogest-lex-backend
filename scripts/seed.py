"""
OroGest Lex — Seed Script
Creates the Director user (Diego Orosa) and sample data.

Usage: python -m scripts.seed
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.security import Role, hash_password
from app.db.session import async_session
from app.models.models import User, Case


async def seed():
    async with async_session() as db:
        # ── 1. Director User ──
        result = await db.execute(select(User).where(User.email == "diego@estudiooro.com"))
        existing = result.scalar_one_or_none()

        if existing:
            print("✅ Director user already exists")
        else:
            director = User(
                email="diego@estudiooro.com",
                hashed_password=hash_password("CambiarEnProduccion2026!"),
                full_name="Dr. Diego Orosa",
                role=Role.DIRECTOR,
                is_active=True,
            )
            db.add(director)
            await db.flush()
            print(f"✅ Director user created: {director.email} (id: {director.id})")

            # ── 2. Sample Cases ──
            sample_cases = [
                Case(
                    case_number="28979/2020",
                    caption="Causa penal — cadena de custodia digital",
                    branch="penal",
                    jurisdiction="CABA",
                    client_name="[CLIENTE MUESTRA]",
                    client_role="imputado",
                    status="activa",
                    assigned_to=director.id,
                    notes="Causa de muestra para testing. Nulidad por extracción WhatsApp sin protocolo forense.",
                ),
                Case(
                    caption="Due diligence — Departamento Palermo",
                    branch="inmobiliario",
                    jurisdiction="CABA",
                    client_name="[INVERSOR MUESTRA]",
                    client_role="comprador",
                    status="en_tramite",
                    assigned_to=director.id,
                    notes="Inmueble de muestra para testing del workflow de due diligence.",
                ),
                Case(
                    caption="Constitución SAS — Cliente España",
                    branch="societario",
                    jurisdiction="CABA",
                    client_name="[CLIENTE MUESTRA ESP]",
                    status="activa",
                    assigned_to=director.id,
                    notes="Caso de muestra: constitución de SAS para cliente con residencia en España.",
                ),
            ]
            db.add_all(sample_cases)
            print(f"✅ {len(sample_cases)} sample cases created")

        await db.commit()
        print("\n🟢 Seed completed successfully")


if __name__ == "__main__":
    asyncio.run(seed())
