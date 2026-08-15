import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.categorization.rapidfuzz_retriever import RapidFuzzAccountRetriever

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_load_reads_seeded_pcg_accounts(db_session: AsyncSession):
    retriever = await RapidFuzzAccountRetriever.load(db_session)
    results = await retriever.search("FRAIS TELECOMMUNICATIONS", top_k=1)
    assert results
    assert results[0].compte_code == "626100"
