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
    siret: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    numero_tva: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    adresse: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    code_postal_ville: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
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


class GrandLivreModel(Base):
    __tablename__ = "grand_livre"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    journal_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    journal_lib: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    ecriture_num: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    ecriture_date: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    compte_num: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    compte_lib: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    comp_aux_num: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="")
    comp_aux_lib: Mapped[str] = mapped_column(sa.String(255), nullable=False, server_default="")
    piece_ref: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    piece_date: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    ecriture_lib: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    debit: Mapped[Decimal] = mapped_column(sa.Numeric(15, 2), nullable=False, server_default="0")
    credit: Mapped[Decimal] = mapped_column(sa.Numeric(15, 2), nullable=False, server_default="0")
    ecriture_let: Mapped[str] = mapped_column(sa.String(10), nullable=False, server_default="")
    date_let: Mapped[dt_date | None] = mapped_column(sa.Date, nullable=True)
    valid_date: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    montantdevise: Mapped[Decimal] = mapped_column(sa.Numeric(15, 2), nullable=False, server_default="0")
    idevise: Mapped[str] = mapped_column(sa.String(3), nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )


class CA3DeclarationModel(Base):
    __tablename__ = "ca3_declarations"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False)
    periode_debut: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    periode_fin: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    raison_sociale: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    adresse: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    code_postal_ville: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)
    siret: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    numero_tva: Mapped[str | None] = mapped_column(sa.String(25), nullable=True)
    a1_ventes: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l08_base: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l08_taxe: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l09_base: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l09_taxe: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l9b_base: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l9b_taxe: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l16_brute: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l19_immos: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l20_autres: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l22_report: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    l23_total_ded: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    tva_due: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    credit_tva: Mapped[Decimal | None] = mapped_column(sa.Numeric(15, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class FactureModel(Base):
    __tablename__ = "factures"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    statut: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="brouillon")
    fournisseur: Mapped[str] = mapped_column(sa.Text, nullable=False)
    date_facture: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    numero_facture: Mapped[str] = mapped_column(sa.String(100), nullable=False, default="")
    montant_ht: Mapped[Decimal] = mapped_column(sa.Numeric(15, 2), nullable=False)
    taux_tva: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), nullable=False, default=20)
    montant_tva: Mapped[Decimal] = mapped_column(sa.Numeric(15, 2), nullable=False)
    montant_ttc: Mapped[Decimal] = mapped_column(sa.Numeric(15, 2), nullable=False)
    compte_charge: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="606100")
    journal_code: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="HA")
    notes: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)


class FactureClientModel(Base):
    __tablename__ = "factures_client"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    type: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="facture")
    statut: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="brouillon")
    numero: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    date_emission: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    date_echeance: Mapped[dt_date | None] = mapped_column(sa.Date, nullable=True)
    client_nom: Mapped[str] = mapped_column(sa.Text, nullable=False)
    client_adresse: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    client_email: Mapped[str] = mapped_column(sa.String(255), nullable=False, default="")
    notes: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)


class LigneFactureClientModel(Base):
    __tablename__ = "lignes_facture_client"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    facture_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    tenant_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    quantite: Mapped[Decimal] = mapped_column(sa.Numeric(10, 3), nullable=False, default=Decimal("1"))
    prix_unitaire: Mapped[Decimal] = mapped_column(sa.Numeric(15, 2), nullable=False)
    taux_tva: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), nullable=False, default=Decimal("20"))
    ordre: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)


class NoteFraisModel(Base):
    __tablename__ = "notes_frais"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False, index=True)
    submitted_by: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False)
    statut: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="soumis")
    date_depense: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    fournisseur: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    montant_ht: Mapped[Decimal] = mapped_column(sa.Numeric(15, 2), nullable=False)
    taux_tva: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), nullable=False, default=Decimal("20"))
    montant_tva: Mapped[Decimal] = mapped_column(sa.Numeric(15, 2), nullable=False)
    montant_ttc: Mapped[Decimal] = mapped_column(sa.Numeric(15, 2), nullable=False)
    compte_charge: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="625000")
    categorie: Mapped[str] = mapped_column(sa.String(100), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)
