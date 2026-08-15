"""Add categorization tables: comptes_pcg (seeded), categorization_patterns, categorization_decisions

comptes_pcg is a global reference table (the French PCG chart of accounts) — it carries no
tenant_id and is not RLS-scoped, unlike every other table in this schema. It is read-only at
runtime for comptis_app (rows only change via a future migration, not application code).

categorization_patterns and categorization_decisions follow the exact same RLS shape as
reconciliation_patterns, using the correct GUC name from the start: 'app.current_organization_id'
(migration 0005 had to retrofix this exact mistake for reconciliation_patterns — see its docstring).

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-15
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (code, libelle, classe) — starter subset of common PME class-6 (charges) accounts from the
# official French PCG. Extend this list in a future migration as coverage gaps are found via
# the evaluation harness (see plan Task 12 / spec §Niveau 4).
_PCG_SEED_ACCOUNTS: list[tuple[str, str, int]] = [
    ("606100", "Achats non stockés de fournitures - eau, énergie", 6),
    ("606400", "Fournitures administratives", 6),
    ("606800", "Autres matières et fournitures", 6),
    ("611000", "Sous-traitance générale", 6),
    ("613200", "Locations immobilières", 6),
    ("613500", "Locations mobilières", 6),
    ("614000", "Charges locatives et de copropriété", 6),
    ("615500", "Entretien et réparations sur biens mobiliers", 6),
    ("615600", "Entretien et réparations sur biens immobiliers", 6),
    ("616100", "Primes d'assurance", 6),
    ("618300", "Documentation technique", 6),
    ("621000", "Personnel extérieur à l'entreprise", 6),
    ("622600", "Honoraires", 6),
    ("622700", "Frais d'actes et de contentieux", 6),
    ("623100", "Annonces et insertions publicitaires", 6),
    ("623400", "Cadeaux à la clientèle", 6),
    ("624100", "Transports sur achats", 6),
    ("624200", "Transports sur ventes", 6),
    ("625100", "Voyages et déplacements", 6),
    ("625600", "Missions", 6),
    ("625700", "Réceptions", 6),
    ("626100", "Frais postaux et de télécommunications", 6),
    ("627000", "Services bancaires et assimilés", 6),
    ("635800", "Autres droits d'enregistrement et de timbre", 6),
    ("658000", "Charges diverses de gestion courante", 6),
    ("641100", "Salaires, appointements", 6),
    ("645100", "Cotisations à l'URSSAF", 6),
]


def upgrade() -> None:
    # --- comptes_pcg: global reference table, no RLS ---
    op.create_table(
        "comptes_pcg",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("libelle", sa.String(255), nullable=False),
        sa.Column("classe", sa.Integer, nullable=False),
    )
    comptes_pcg_table = sa.table(
        "comptes_pcg",
        sa.column("id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("libelle", sa.String),
        sa.column("classe", sa.Integer),
    )
    op.bulk_insert(
        comptes_pcg_table,
        [
            {"id": uuid.uuid4(), "code": code, "libelle": libelle, "classe": classe}
            for code, libelle, classe in _PCG_SEED_ACCOUNTS
        ],
    )
    op.execute("GRANT SELECT ON comptes_pcg TO comptis_app")

    # --- categorization_patterns ---
    op.create_table(
        "categorization_patterns",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("libelle_pattern", sa.String(255), nullable=False),
        sa.Column("fournisseur", sa.String(255), nullable=False),
        sa.Column("compte_code", sa.String(20), nullable=False),
        sa.Column("occurrence_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "libelle_pattern", "fournisseur", name="uq_cp_tenant_libelle_fournisseur"
        ),
    )
    op.create_index(
        "ix_categorization_patterns_tenant_libelle",
        "categorization_patterns",
        ["tenant_id", "libelle_pattern"],
    )
    op.execute("ALTER TABLE categorization_patterns ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE categorization_patterns FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY cp_org_isolation ON categorization_patterns
            USING (
                tenant_id IN (
                    SELECT id FROM tenants
                    WHERE organization_id = current_setting('app.current_organization_id', true)::uuid
                )
            )
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON categorization_patterns TO comptis_app")

    # --- categorization_decisions ---
    op.create_table(
        "categorization_decisions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("ecriture_id", sa.Uuid, nullable=False),
        sa.Column("compte_code", sa.String(20), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column(
            "validated_by", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ecriture_id", name="uq_cd_ecriture"),
    )
    op.execute("ALTER TABLE categorization_decisions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE categorization_decisions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY cd_org_isolation ON categorization_decisions
            USING (
                tenant_id IN (
                    SELECT id FROM tenants
                    WHERE organization_id = current_setting('app.current_organization_id', true)::uuid
                )
            )
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON categorization_decisions TO comptis_app")


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON categorization_decisions FROM comptis_app")
    op.execute("DROP POLICY IF EXISTS cd_org_isolation ON categorization_decisions")
    op.drop_table("categorization_decisions")

    op.execute("REVOKE ALL PRIVILEGES ON categorization_patterns FROM comptis_app")
    op.execute("DROP POLICY IF EXISTS cp_org_isolation ON categorization_patterns")
    op.drop_index("ix_categorization_patterns_tenant_libelle", table_name="categorization_patterns")
    op.drop_table("categorization_patterns")

    op.execute("REVOKE ALL PRIVILEGES ON comptes_pcg FROM comptis_app")
    op.drop_table("comptes_pcg")
