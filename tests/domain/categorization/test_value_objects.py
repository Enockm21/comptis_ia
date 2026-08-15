from comptis.domain.categorization.value_objects import CategorizationSource, CategorizationStatut


def test_categorization_source_values():
    assert CategorizationSource.PATTERN == "pattern"
    assert CategorizationSource.RAG == "rag"


def test_categorization_statut_values():
    assert CategorizationStatut.AUTO_VALIDATED == "auto_validated"
    assert CategorizationStatut.PENDING_REVIEW == "pending_review"
    assert CategorizationStatut.HUMAN_VALIDATED == "human_validated"


def test_categorization_source_is_string():
    assert isinstance(CategorizationSource.PATTERN, str)
