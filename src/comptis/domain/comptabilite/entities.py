from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from .value_objects import StatutEcriture


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class CompteComptable:
    tenant_id: UUID
    numero: str
    libelle: str
    classe: int
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass
class Ecriture:
    tenant_id: UUID
    transaction_id: str
    facture_id: str
    montant: Decimal
    date: date_
    compte_id: UUID | None = None
    statut: StatutEcriture = StatutEcriture.A_CATEGORISER
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass
class LigneGrandLivre:
    """Ligne de grand livre au format FEC (Fichier des Écritures Comptables — art. L13 LPF)."""
    tenant_id: UUID
    journal_code: str        # JournalCode
    journal_lib: str         # JournalLib
    ecriture_num: str        # EcritureNum — numéro dans le journal
    ecriture_date: date_     # EcritureDate
    compte_num: str          # CompteNum (PCG)
    compte_lib: str          # CompteLib
    piece_ref: str           # PieceRef
    piece_date: date_        # PieceDate
    ecriture_lib: str        # EcritureLib
    debit: Decimal           # Debit (0 si écriture créditrice)
    credit: Decimal          # Credit (0 si écriture débitrice)
    valid_date: date_        # ValidDate
    comp_aux_num: str = ""   # CompAuxNum (tiers)
    comp_aux_lib: str = ""   # CompAuxLib
    ecriture_let: str = ""   # EcritureLet
    date_let: date_ | None = None
    montantdevise: Decimal = field(default_factory=lambda: Decimal("0"))
    idevise: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
