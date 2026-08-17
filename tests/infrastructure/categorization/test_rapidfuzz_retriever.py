from comptis.domain.categorization.entities import CompteComptable
from comptis.domain.categorization.value_objects import CategorizationSource
from comptis.infrastructure.categorization.rapidfuzz_retriever import RapidFuzzAccountRetriever


def _comptes() -> list[CompteComptable]:
    return [
        CompteComptable(code="626100", libelle="Frais postaux et de télécommunications", classe=6),
        CompteComptable(code="613500", libelle="Locations mobilières", classe=6),
        CompteComptable(code="625700", libelle="Réceptions", classe=6),
    ]


async def test_search_finds_close_match():
    retriever = RapidFuzzAccountRetriever(_comptes())
    results = await retriever.search("FRAIS TELECOMMUNICATIONS", top_k=3)
    assert results
    assert results[0].compte_code == "626100"
    assert results[0].source == CategorizationSource.RAG
    assert 0.0 < results[0].confidence <= 1.0


async def test_search_excludes_weak_matches():
    retriever = RapidFuzzAccountRetriever(_comptes())
    results = await retriever.search("XYZQWERTY UNRELATED TEXT 12345", top_k=3)
    assert all(r.confidence >= 0.4 for r in results)


async def test_search_on_empty_reference_set_returns_empty():
    retriever = RapidFuzzAccountRetriever([])
    results = await retriever.search("anything")
    assert results == []


async def test_search_result_carries_evidence():
    retriever = RapidFuzzAccountRetriever(_comptes())
    results = await retriever.search("RECEPTION CLIENT", top_k=1)
    assert results[0].evidence
    assert "625700" in results[0].evidence[0]


def test_comptes_property_exposes_reference_set():
    comptes = _comptes()
    retriever = RapidFuzzAccountRetriever(comptes)
    assert retriever.comptes == comptes
