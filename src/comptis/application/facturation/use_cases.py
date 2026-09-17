from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import anthropic


@dataclass
class FactureExtraite:
    fournisseur: str
    date_facture: date
    numero_facture: str
    montant_ht: Decimal
    taux_tva: Decimal
    montant_tva: Decimal
    montant_ttc: Decimal
    compte_charge: str
    journal_code: str = "HA"
    notes: str = ""


_SYSTEM = """Tu es un expert-comptable français. Analyse la facture fournie et extrais les données en JSON strict.

Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ni après, avec exactement ces clés :
{
  "fournisseur": "Nom du fournisseur",
  "date_facture": "YYYY-MM-DD",
  "numero_facture": "Numéro de la facture",
  "montant_ht": 0.00,
  "taux_tva": 20.0,
  "montant_tva": 0.00,
  "montant_ttc": 0.00,
  "compte_charge": "606100",
  "notes": "Observations éventuelles"
}

Règles :
- montant_ht, montant_tva, montant_ttc sont des nombres décimaux (pas de chaînes)
- taux_tva: 0, 5.5, 10, ou 20
- compte_charge: utilise le plan comptable français général (classe 6)
  - 601xxx Achats de matières premières
  - 606xxx Achats non stockés (fournitures, eau, énergie)
  - 607xxx Achats de marchandises
  - 611xxx Sous-traitance
  - 613xxx Loyers
  - 615xxx Entretien et réparations
  - 616xxx Primes d'assurance
  - 622xxx Honoraires (avocat, expert-comptable)
  - 623xxx Publicité, marketing
  - 624xxx Transports et déplacements
  - 625xxx Frais de déplacements
  - 626xxx Frais postaux et télécommunications
  - 627xxx Services bancaires
- Si tu ne peux pas lire la facture clairement, mets les montants à 0 et notes tes doutes dans "notes"
"""


class AnalyserFactureOCR:
    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = anthropic.Anthropic(api_key=api_key)

    async def execute(self, file_bytes: bytes, media_type: str) -> FactureExtraite:
        b64 = base64.standard_b64encode(file_bytes).decode()

        if media_type == "application/pdf":
            content_block: dict = {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
            }
        else:
            # image/jpeg or image/png
            img_mt = media_type if media_type in ("image/jpeg", "image/png", "image/webp", "image/gif") else "image/jpeg"
            content_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": img_mt, "data": b64},
            }

        message = self._client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    content_block,
                    {"type": "text", "text": "Extrais les données de cette facture en JSON."},
                ],
            }],
        )

        raw = message.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)

        return FactureExtraite(
            fournisseur=str(data.get("fournisseur", "")),
            date_facture=date.fromisoformat(data.get("date_facture", str(date.today()))),
            numero_facture=str(data.get("numero_facture", "")),
            montant_ht=Decimal(str(data.get("montant_ht", "0"))),
            taux_tva=Decimal(str(data.get("taux_tva", "20"))),
            montant_tva=Decimal(str(data.get("montant_tva", "0"))),
            montant_ttc=Decimal(str(data.get("montant_ttc", "0"))),
            compte_charge=str(data.get("compte_charge", "606100")),
            notes=str(data.get("notes", "")),
        )
