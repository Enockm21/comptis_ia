from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import anthropic


@dataclass
class DepenseExtraite:
    date_depense: date
    fournisseur: str
    description: str
    montant_ht: Decimal
    taux_tva: Decimal
    montant_tva: Decimal
    montant_ttc: Decimal
    compte_charge: str
    categorie: str


_SYSTEM = """Tu es un expert-comptable français. Analyse ce justificatif de dépense (ticket, reçu, facture) et extrais les données en JSON strict.

Réponds UNIQUEMENT avec un objet JSON, sans texte autour :
{
  "date_depense": "YYYY-MM-DD",
  "fournisseur": "Nom du commerce/fournisseur",
  "description": "Description courte de la dépense",
  "montant_ht": 0.00,
  "taux_tva": 20.0,
  "montant_tva": 0.00,
  "montant_ttc": 0.00,
  "compte_charge": "625000",
  "categorie": "Restauration"
}

Règles compte_charge selon PCG français :
- Repas, restaurants → 625100
- Transport (taxi, train, avion) → 625110
- Hébergement (hôtel) → 625120
- Carburant → 624500
- Fournitures de bureau → 606400
- Matériel informatique (<500€) → 606300
- Abonnements logiciels → 626000
- Téléphone, internet → 626000
- Livres, formations → 618000
- Cadeaux clients → 623300
- Autres frais divers → 625000

Catégories possibles : Restauration, Transport, Hébergement, Carburant, Fournitures, Informatique, Télécom, Formation, Cadeau, Autre

Si montant TTC visible sans HT, calcule HT = TTC / (1 + taux_tva/100).
"""


class AnalyserDepenseOCR:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    async def execute(self, file_bytes: bytes, media_type: str) -> DepenseExtraite:
        b64 = base64.standard_b64encode(file_bytes).decode()

        if media_type == "application/pdf":
            block: dict = {"type": "document",
                           "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
        else:
            img_mt = media_type if media_type in ("image/jpeg", "image/png", "image/webp") else "image/jpeg"
            block = {"type": "image",
                     "source": {"type": "base64", "media_type": img_mt, "data": b64}}

        msg = self._client.messages.create(
            model="claude-sonnet-5",
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": [
                block,
                {"type": "text", "text": "Extrais les données de ce justificatif."},
            ]}],
        )

        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())

        return DepenseExtraite(
            date_depense=date.fromisoformat(data.get("date_depense", str(date.today()))),
            fournisseur=str(data.get("fournisseur", "")),
            description=str(data.get("description", "")),
            montant_ht=Decimal(str(data.get("montant_ht", "0"))),
            taux_tva=Decimal(str(data.get("taux_tva", "20"))),
            montant_tva=Decimal(str(data.get("montant_tva", "0"))),
            montant_ttc=Decimal(str(data.get("montant_ttc", "0"))),
            compte_charge=str(data.get("compte_charge", "625000")),
            categorie=str(data.get("categorie", "Autre")),
        )
