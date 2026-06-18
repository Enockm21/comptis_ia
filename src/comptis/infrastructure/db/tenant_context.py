from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_context(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    organization_id: UUID | None = None,
    user_id: UUID | None = None,
) -> None:
    """Set Postgres session variables for RLS. Must be called inside an open transaction.

    Uses set_config(name, value, true) — the parameterizable equivalent of SET LOCAL —
    so variables are scoped to the current transaction only, safe with connection
    pooling in transaction mode.
    """
    vars_to_set = {
        "app.current_tenant_id": tenant_id,
        "app.current_organization_id": organization_id,
        "app.current_user_id": user_id,
    }
    for var, value in vars_to_set.items():
        if value is not None:
            # Postgres SET does not accept bind parameters, so we pass the value
            # via set_config(), which does support a normal query parameter.
            await session.execute(
                text("SELECT set_config(:name, :value, true)"),
                {"name": var, "value": str(value)},
            )
