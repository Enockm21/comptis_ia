from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture
from comptis.infrastructure.db.comptabilite_repository import (
    SQLAlchemyCompteComptableRepository,
    SQLAlchemyEcritureRepository,
)
from comptis.infrastructure.db.tenant_context import set_tenant_context

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_save_and_list_compte_comptable(db_session, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await set_tenant_context(db_session, tenant_id=tenant_id, organization_id=org_id)
    repo = SQLAlchemyCompteComptableRepository(db_session)

    compte = CompteComptable(tenant_id=tenant_id, numero="625100", libelle="Voyages", classe=6)
    await repo.save(compte)

    comptes = await repo.list_by_tenant(tenant_id)
    assert len(comptes) == 1
    assert comptes[0].numero == "625100"
    assert comptes[0].libelle == "Voyages"


@pytest.mark.integration
async def test_save_compte_comptable_is_idempotent_on_conflict(db_session, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await set_tenant_context(db_session, tenant_id=tenant_id, organization_id=org_id)
    repo = SQLAlchemyCompteComptableRepository(db_session)

    await repo.save(CompteComptable(tenant_id=tenant_id, numero="606400", libelle="Fournitures", classe=6))
    await repo.save(CompteComptable(tenant_id=tenant_id, numero="606400", libelle="Fournitures (rejoué)", classe=6))

    comptes = await repo.list_by_tenant(tenant_id)
    matching = [c for c in comptes if c.numero == "606400"]
    assert len(matching) == 1


@pytest.mark.integration
async def test_save_and_retrieve_ecriture(db_session, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await set_tenant_context(db_session, tenant_id=tenant_id, organization_id=org_id)
    repo = SQLAlchemyEcritureRepository(db_session)

    ecriture = Ecriture(
        tenant_id=tenant_id, transaction_id="t1", facture_id="f1",
        montant=Decimal("7.10"), date=date(2026, 7, 31),
    )
    await repo.save(ecriture)

    from sqlalchemy import select
    from comptis.infrastructure.db.models import EcritureModel
    result = await db_session.execute(select(EcritureModel).where(EcritureModel.tenant_id == tenant_id))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].transaction_id == "t1"
    assert rows[0].compte_id is None
    assert rows[0].statut == "a_categoriser"


@pytest.mark.integration
async def test_save_ecriture_is_idempotent_on_same_transaction(db_session, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await set_tenant_context(db_session, tenant_id=tenant_id, organization_id=org_id)
    repo = SQLAlchemyEcritureRepository(db_session)

    await repo.save(Ecriture(tenant_id=tenant_id, transaction_id="t2", facture_id="f2", montant=Decimal("5"), date=date(2026, 1, 1)))
    await repo.save(Ecriture(tenant_id=tenant_id, transaction_id="t2", facture_id="f2", montant=Decimal("5"), date=date(2026, 1, 1)))

    from sqlalchemy import select
    from comptis.infrastructure.db.models import EcritureModel
    result = await db_session.execute(select(EcritureModel).where(EcritureModel.transaction_id == "t2"))
    assert len(result.scalars().all()) == 1
