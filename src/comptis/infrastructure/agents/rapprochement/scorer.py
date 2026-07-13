from __future__ import annotations

from datetime import date
from decimal import Decimal

from rapidfuzz import fuzz

from comptis.domain.rapprochement.entities import Facture, Transaction


WEIGHT_TEXT = 0.40
WEIGHT_AMOUNT = 0.35
WEIGHT_DATE = 0.25
DATE_WINDOW_DAYS = 30


def compute_composite_score(transaction: Transaction, facture: Facture) -> float:
    text_score = fuzz.token_sort_ratio(transaction.libelle, facture.fournisseur) / 100.0

    if transaction.montant == Decimal("0"):
        amount_score = 0.0
    else:
        amount_score = max(
            0.0,
            1.0 - float(abs(transaction.montant - facture.montant) / abs(transaction.montant)),
        )

    date_diff = abs((transaction.date - facture.date).days)
    date_score = max(0.0, 1.0 - date_diff / DATE_WINDOW_DAYS)

    return WEIGHT_TEXT * text_score + WEIGHT_AMOUNT * amount_score + WEIGHT_DATE * date_score


def prefilter_candidates(transaction: Transaction, factures: list[Facture]) -> list[Facture]:
    """Return factures within ±10% montant and ±30 days, statut non_rapprochee."""
    t_montant = transaction.montant
    lower = t_montant * Decimal("0.90")
    upper = t_montant * Decimal("1.10")
    t_date = transaction.date

    return [
        f for f in factures
        if f.statut_rapprochement == "non_rapprochee"
        and lower <= f.montant <= upper
        and abs((f.date - t_date).days) <= DATE_WINDOW_DAYS
    ]
