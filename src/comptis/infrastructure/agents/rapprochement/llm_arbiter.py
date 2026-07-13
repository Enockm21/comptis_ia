from __future__ import annotations

import json
import os
from decimal import Decimal

from langchain_anthropic import ChatAnthropic

from comptis.domain.rapprochement.entities import Facture, Transaction

LLM_MODEL = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")
CONFIDENCE_THRESHOLD = float(os.environ.get("RECONCILIATION_CONFIDENCE_THRESHOLD", "0.85"))

_PROMPT_TEMPLATE = """\
You are an accounting assistant. Decide if a bank transaction matches an invoice.

Transaction:
- Label: {libelle}
- Amount: {t_montant} EUR
- Date: {t_date}

Invoice:
- Supplier: {fournisseur}
- Amount: {f_montant} EUR
- Date: {f_date}

Reply ONLY with a JSON object: {{"confidence": <float 0.0-1.0>, "reason": "<one sentence>"}}
"""


class LLMArbiter:
    def __init__(self, model: str = LLM_MODEL) -> None:
        self._llm = ChatAnthropic(model=model, max_tokens=128)

    async def judge(self, transaction: Transaction, facture: Facture) -> float:
        prompt = _PROMPT_TEMPLATE.format(
            libelle=transaction.libelle,
            t_montant=transaction.montant,
            t_date=transaction.date,
            fournisseur=facture.fournisseur,
            f_montant=facture.montant,
            f_date=facture.date,
        )
        response = await self._llm.ainvoke(prompt)
        try:
            data = json.loads(response.content)
            return float(data["confidence"])
        except (json.JSONDecodeError, KeyError, ValueError):
            return 0.0
