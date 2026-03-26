"""
OroGest Lex — CLI Management Tool
Admin operations from the terminal.

Usage:
    python -m scripts.cli seed              # Seed initial data
    python -m scripts.cli create-user       # Create a new user
    python -m scripts.cli list-users        # List all users
    python -m scripts.cli reset-password    # Reset user password
    python -m scripts.cli stats             # System statistics
    python -m scripts.cli verify-audit      # Verify audit chain integrity
    python -m scripts.cli seed-templates    # Load system writing templates
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from sqlalchemy import func, select

from app.core.security import Role, hash_password, compute_audit_hash
from app.db.session import async_session
from app.models.models import (
    User, Case, Document, Property, AIConversation, AuditLog, Client, WritingTemplate,
)


async def cmd_seed():
    """Create director user and sample data."""
    from scripts.seed import seed
    await seed()


async def cmd_create_user():
    """Interactive user creation."""
    print("═══ Crear usuario ═══")
    email = input("Email: ").strip()
    name = input("Nombre completo: ").strip()
    role = input("Rol (director/abogado/asistente/pasante): ").strip()
    password = input("Contraseña (min 8 chars): ").strip()

    if not all([email, name, role, password]) or len(password) < 8:
        print("❌ Datos incompletos o contraseña muy corta")
        return

    if role not in [r.value for r in Role]:
        print(f"❌ Rol inválido. Opciones: {[r.value for r in Role]}")
        return

    async with async_session() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"❌ Email ya registrado: {email}")
            return

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=name,
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        print(f"✅ Usuario creado: {email} (rol: {role}, id: {user.id})")


async def cmd_list_users():
    """List all users."""
    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.is_deleted == False).order_by(User.created_at.desc())
        )
        users = result.scalars().all()

        print(f"\n{'Email':<30} {'Nombre':<25} {'Rol':<12} {'Activo':<8} {'Último login'}")
        print("─" * 100)
        for u in users:
            login = u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "nunca"
            active = "✅" if u.is_active else "❌"
            print(f"{u.email:<30} {u.full_name:<25} {u.role:<12} {active:<8} {login}")
        print(f"\nTotal: {len(users)} usuarios")


async def cmd_reset_password():
    """Reset a user's password."""
    email = input("Email del usuario: ").strip()
    new_password = input("Nueva contraseña (min 8): ").strip()

    if len(new_password) < 8:
        print("❌ Contraseña muy corta")
        return

    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            print(f"❌ Usuario no encontrado: {email}")
            return

        user.hashed_password = hash_password(new_password)
        await db.commit()
        print(f"✅ Contraseña actualizada para {email}")


async def cmd_stats():
    """Show system statistics."""
    async with async_session() as db:
        counts = {}
        for model, name in [
            (User, "Usuarios"),
            (Case, "Causas"),
            (Document, "Documentos"),
            (Property, "Propiedades"),
            (Client, "Clientes"),
            (AIConversation, "Conversaciones IA"),
            (AuditLog, "Eventos audit"),
            (WritingTemplate, "Plantillas"),
        ]:
            try:
                result = await db.execute(select(func.count()).select_from(model))
                counts[name] = result.scalar() or 0
            except Exception:
                counts[name] = "N/D"

        # AI tokens
        try:
            result = await db.execute(select(func.sum(AIConversation.tokens_used)))
            total_tokens = result.scalar() or 0
        except Exception:
            total_tokens = "N/D"

        print("\n═══ OroGest Lex — Estadísticas ═══\n")
        for name, count in counts.items():
            print(f"  {name:<25} {count:>8}")
        print(f"\n  {'Tokens IA consumidos':<25} {total_tokens:>8}")
        print()


async def cmd_verify_audit():
    """Verify audit log chain integrity."""
    async with async_session() as db:
        result = await db.execute(
            select(AuditLog).order_by(AuditLog.timestamp.asc())
        )
        entries = result.scalars().all()

        if not entries:
            print("ℹ️  No hay entradas en el audit log")
            return

        broken_links = 0
        for i in range(1, len(entries)):
            if entries[i].previous_hash != entries[i - 1].current_hash:
                broken_links += 1
                print(f"  ❌ Cadena rota en entrada {i}: {entries[i].action} ({entries[i].timestamp})")

        total = len(entries)
        if broken_links == 0:
            print(f"✅ Cadena de auditoría íntegra: {total} entradas verificadas")
        else:
            print(f"\n⚠️  {broken_links} enlaces rotos en {total} entradas")


async def cmd_seed_templates():
    """Load system writing templates."""
    from app.api.v1.endpoints.templates import SYSTEM_TEMPLATES

    async with async_session() as db:
        # Get director user
        result = await db.execute(
            select(User).where(User.role == Role.DIRECTOR, User.is_active == True).limit(1)
        )
        director = result.scalar_one_or_none()
        if not director:
            print("❌ No hay usuario director. Ejecutar 'seed' primero.")
            return

        created = 0
        for tpl_data in SYSTEM_TEMPLATES:
            existing = await db.execute(
                select(WritingTemplate).where(
                    WritingTemplate.name == tpl_data["name"],
                    WritingTemplate.is_system == True,
                )
            )
            if existing.scalar_one_or_none():
                print(f"  ⏭️  Ya existe: {tpl_data['name']}")
                continue

            template = WritingTemplate(
                name=tpl_data["name"],
                description=tpl_data["description"],
                branch=tpl_data["branch"],
                doc_type=tpl_data["doc_type"],
                template_content=tpl_data["template_content"],
                variables_schema=tpl_data["variables_schema"],
                created_by=director.id,
                is_system=True,
            )
            db.add(template)
            created += 1
            print(f"  ✅ Creada: {tpl_data['name']}")

        await db.commit()
        print(f"\n🟢 {created} plantillas creadas")


def main():
    parser = argparse.ArgumentParser(
        description="OroGest Lex — CLI de administración",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=[
            "seed", "create-user", "list-users", "reset-password",
            "stats", "verify-audit", "seed-templates",
        ],
        help=(
            "seed             Crear datos iniciales (director + muestras)\n"
            "create-user      Crear nuevo usuario interactivamente\n"
            "list-users       Listar todos los usuarios\n"
            "reset-password   Resetear contraseña de un usuario\n"
            "stats            Estadísticas del sistema\n"
            "verify-audit     Verificar integridad del audit log\n"
            "seed-templates   Cargar plantillas de escritos del sistema"
        ),
    )

    args = parser.parse_args()

    commands = {
        "seed": cmd_seed,
        "create-user": cmd_create_user,
        "list-users": cmd_list_users,
        "reset-password": cmd_reset_password,
        "stats": cmd_stats,
        "verify-audit": cmd_verify_audit,
        "seed-templates": cmd_seed_templates,
    }

    asyncio.run(commands[args.command]())


if __name__ == "__main__":
    main()
