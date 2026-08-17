import pytest

from comptis.domain.categorization.exceptions import CategorizationDecisionNotFoundError


def test_can_be_raised_and_caught():
    with pytest.raises(CategorizationDecisionNotFoundError, match="no decision"):
        raise CategorizationDecisionNotFoundError("no decision for this ecriture")
