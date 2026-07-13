from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from comptis.domain.rapprochement.entities import Facture, Transaction
from comptis.infrastructure.agents.rapprochement.llm_arbiter import LLMArbiter


def _t() -> Transaction:
    return Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="FACTURE ABC SARL")


def _f() -> Facture:
    return Facture(id="f1", montant=Decimal("100.00"), date=date(2026, 1, 15),
                   fournisseur="ABC SARL", statut_rapprochement="non_rapprochee")


@pytest.mark.asyncio
async def test_judge_returns_confidence_from_llm():
    mock_response = MagicMock()
    mock_response.content = '{"confidence": 0.92, "reason": "Same supplier and amount"}'

    with patch('comptis.infrastructure.agents.rapprochement.llm_arbiter.ChatAnthropic') as mock_llm_class:
        mock_instance = MagicMock()
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_class.return_value = mock_instance

        arbiter = LLMArbiter()
        result = await arbiter.judge(_t(), _f())

    assert result == pytest.approx(0.92)


@pytest.mark.asyncio
async def test_judge_returns_zero_on_invalid_json():
    mock_response = MagicMock()
    mock_response.content = "not json at all"

    with patch('comptis.infrastructure.agents.rapprochement.llm_arbiter.ChatAnthropic') as mock_llm_class:
        mock_instance = MagicMock()
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_class.return_value = mock_instance

        arbiter = LLMArbiter()
        result = await arbiter.judge(_t(), _f())

    assert result == 0.0


@pytest.mark.asyncio
async def test_judge_returns_zero_on_missing_key():
    mock_response = MagicMock()
    mock_response.content = '{"reason": "no confidence key"}'

    with patch('comptis.infrastructure.agents.rapprochement.llm_arbiter.ChatAnthropic') as mock_llm_class:
        mock_instance = MagicMock()
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_class.return_value = mock_instance

        arbiter = LLMArbiter()
        result = await arbiter.judge(_t(), _f())

    assert result == 0.0
