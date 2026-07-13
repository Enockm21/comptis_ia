import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID, uuid4
from datetime import datetime, timezone
from decimal import Decimal

from .base import Base


def _uuid() -> UUID:
    return uuid4()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )


class TenantModel(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    organization_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(sa.String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )


class MembershipModel(Base):
    __tablename__ = "memberships"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="viewer")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (sa.UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),)


class ApiKeyModel(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    organization_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )


class ReconciliationPatternModel(Base):
    __tablename__ = "reconciliation_patterns"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    libelle_pattern: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    fournisseur: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    montant_approx: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    last_seen_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)

    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "libelle_pattern", "fournisseur", name="uq_rp_tenant_libelle_fournisseur"),
    )
