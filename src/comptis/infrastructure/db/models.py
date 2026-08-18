import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID, uuid4
from datetime import date as dt_date, datetime, timezone
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


class OrgIntegrationModel(Base):
    __tablename__ = "org_integrations"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    organization_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    api_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    mcp_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    token_encrypted: Mapped[bytes | None] = mapped_column(sa.LargeBinary, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        sa.UniqueConstraint("organization_id", "name", name="uq_org_integration_org_name"),
    )


class CompteComptableModel(Base):
    __tablename__ = "comptes_pcg"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(sa.String(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    classe: Mapped[int] = mapped_column(sa.Integer, nullable=False)


class CategorizationPatternModel(Base):
    __tablename__ = "categorization_patterns"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    libelle_pattern: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    fournisseur: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    compte_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id", "libelle_pattern", "fournisseur", name="uq_cp_tenant_libelle_fournisseur"
        ),
    )


class CategorizationDecisionModel(Base):
    __tablename__ = "categorization_decisions"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ecriture_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False)
    compte_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    statut: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)
    validated_by: Mapped[UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (sa.UniqueConstraint("ecriture_id", name="uq_cd_ecriture"),)


class PlanComptableModel(Base):
    __tablename__ = "plan_comptable"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    numero: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    libelle: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    classe: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "numero", name="uq_plan_comptable_tenant_numero"),
    )


class EcritureModel(Base):
    __tablename__ = "ecritures"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    transaction_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    facture_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    montant: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    date: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    compte_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("plan_comptable.id", ondelete="SET NULL"), nullable=True
    )
    statut: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="a_categoriser")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "transaction_id", name="uq_ecritures_tenant_transaction"),
    )


class ReconciliationRunModel(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False)
    date_debut: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    date_fin: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    total_transactions: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    total_rapprochees: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    total_ecarts: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    total_non_rapprochees: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    statut: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="en_cours")
    ran_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)


class TVADeclarationModel(Base):
    __tablename__ = "tva_declarations"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False)
    date_debut: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    date_fin: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    tva_collectee: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False, default=Decimal("0"))
    tva_deductible: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False, default=Decimal("0"))
    tva_nette: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False, default=Decimal("0"))
    lignes: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=list)
    statut: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="brouillon")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)
    deposee_le: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    payee_le: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
