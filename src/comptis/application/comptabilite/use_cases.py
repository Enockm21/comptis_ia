from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture, LigneGrandLivre

from .ports import CompteComptableRepository, EcritureRepository, GrandLivreRepository, PlanComptableSource

# ── FEC column order (DGFiP spec) ──────────────────────────────────────────────
_FEC_HEADERS = [
    "JournalCode", "JournalLib", "EcritureNum", "EcritureDate",
    "CompteNum", "CompteLib", "CompAuxNum", "CompAuxLib",
    "PieceRef", "PieceDate", "EcritureLib",
    "Debit", "Credit", "EcritureLet", "DateLet", "ValidDate",
    "Montantdevise", "Idevise",
]
_DATE_FMT = "%Y%m%d"


def _parse_fec_date(s: str) -> date:
    s = s.strip()
    if not s:
        return date(1900, 1, 1)
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _parse_amount(s: str) -> Decimal:
    s = s.strip().replace(",", ".")
    try:
        return Decimal(s) if s else Decimal("0")
    except InvalidOperation:
        return Decimal("0")


def _fmt_date(d: date) -> str:
    return d.strftime(_DATE_FMT)


def _fmt_amount(v: Decimal) -> str:
    return f"{v:.2f}"


@dataclass
class ImporterPlanComptable:
    compte_repo: CompteComptableRepository
    source: PlanComptableSource

    async def execute(self, tenant_id: UUID) -> list[CompteComptable]:
        comptes = []
        for numero, libelle in await self.source.list_comptes():
            classe = int(numero[0]) if numero[:1].isdigit() else 0
            compte = CompteComptable(
                tenant_id=tenant_id, numero=numero, libelle=libelle, classe=classe,
            )
            await self.compte_repo.save(compte)
            comptes.append(compte)
        return comptes


@dataclass
class CreerEcritureDepuisMatch:
    ecriture_repo: EcritureRepository

    async def execute(
        self,
        tenant_id: UUID,
        transaction_id: str,
        facture_id: str,
        montant: Decimal,
        date_: date,
    ) -> Ecriture:
        ecriture = Ecriture(
            tenant_id=tenant_id,
            transaction_id=transaction_id,
            facture_id=facture_id,
            montant=montant,
            date=date_,
        )
        await self.ecriture_repo.save(ecriture)
        return ecriture


@dataclass
class ImporterFEC:
    """Parse un fichier FEC (CSV |-séparé) et persiste les lignes dans le grand livre."""
    repo: GrandLivreRepository

    async def execute(self, tenant_id: UUID, content: bytes) -> int:
        text = content.decode("utf-8-sig")  # handle BOM
        reader = csv.DictReader(io.StringIO(text), delimiter="|")
        lignes: list[LigneGrandLivre] = []
        for row in reader:
            dl = row.get("DateLet", "").strip()
            lignes.append(LigneGrandLivre(
                tenant_id=tenant_id,
                journal_code=row.get("JournalCode", "").strip(),
                journal_lib=row.get("JournalLib", "").strip(),
                ecriture_num=row.get("EcritureNum", "").strip(),
                ecriture_date=_parse_fec_date(row.get("EcritureDate", "")),
                compte_num=row.get("CompteNum", "").strip(),
                compte_lib=row.get("CompteLib", "").strip(),
                comp_aux_num=row.get("CompAuxNum", "").strip(),
                comp_aux_lib=row.get("CompAuxLib", "").strip(),
                piece_ref=row.get("PieceRef", "").strip(),
                piece_date=_parse_fec_date(row.get("PieceDate", "") or row.get("EcritureDate", "")),
                ecriture_lib=row.get("EcritureLib", "").strip(),
                debit=_parse_amount(row.get("Debit", "0")),
                credit=_parse_amount(row.get("Credit", "0")),
                ecriture_let=row.get("EcritureLet", "").strip(),
                date_let=_parse_fec_date(dl) if dl else None,
                valid_date=_parse_fec_date(row.get("ValidDate", "") or row.get("EcritureDate", "")),
                montantdevise=_parse_amount(row.get("Montantdevise", "0")),
                idevise=row.get("Idevise", "").strip(),
            ))
        return await self.repo.save_many(lignes)


@dataclass
class ExporterFEC:
    """Génère le FEC au format DGFiP en mémoire."""
    repo: GrandLivreRepository

    async def execute(
        self, tenant_id: UUID, date_debut: date | None = None, date_fin: date | None = None
    ) -> bytes:
        lignes = await self.repo.list_by_tenant(tenant_id, date_debut, date_fin)
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="|", lineterminator="\r\n")
        writer.writerow(_FEC_HEADERS)
        for lg in lignes:
            writer.writerow([
                lg.journal_code, lg.journal_lib, lg.ecriture_num,
                _fmt_date(lg.ecriture_date),
                lg.compte_num, lg.compte_lib,
                lg.comp_aux_num, lg.comp_aux_lib,
                lg.piece_ref, _fmt_date(lg.piece_date),
                lg.ecriture_lib,
                _fmt_amount(lg.debit), _fmt_amount(lg.credit),
                lg.ecriture_let,
                _fmt_date(lg.date_let) if lg.date_let else "",
                _fmt_date(lg.valid_date),
                _fmt_amount(lg.montantdevise), lg.idevise,
            ])
        return buf.getvalue().encode("utf-8")


# ── Résultats des états financiers ─────────────────────────────────────────────

@dataclass
class PosteBalance:
    compte_num: str
    compte_lib: str
    total_debit: Decimal
    total_credit: Decimal

    @property
    def solde_debiteur(self) -> Decimal:
        d = self.total_debit - self.total_credit
        return d if d > 0 else Decimal("0")

    @property
    def solde_crediteur(self) -> Decimal:
        d = self.total_credit - self.total_debit
        return d if d > 0 else Decimal("0")


@dataclass
class CalculerBalance:
    """Balance générale des comptes sur une période."""
    repo: GrandLivreRepository

    async def execute(
        self, tenant_id: UUID, date_debut: date | None = None, date_fin: date | None = None
    ) -> list[PosteBalance]:
        lignes = await self.repo.list_by_tenant(tenant_id, date_debut, date_fin)
        totaux: dict[str, PosteBalance] = {}
        for lg in lignes:
            if lg.compte_num not in totaux:
                totaux[lg.compte_num] = PosteBalance(
                    compte_num=lg.compte_num, compte_lib=lg.compte_lib,
                    total_debit=Decimal("0"), total_credit=Decimal("0"),
                )
            totaux[lg.compte_num].total_debit += lg.debit
            totaux[lg.compte_num].total_credit += lg.credit
        return sorted(totaux.values(), key=lambda p: p.compte_num)


@dataclass
class PosteBilan:
    classe: int
    libelle: str
    montant: Decimal
    side: str  # "actif" | "passif"


_BILAN_CLASSES = {
    1: ("Capitaux propres et dettes LT", "passif"),
    2: ("Immobilisations", "actif"),
    3: ("Stocks", "actif"),
    4: ("Créances (actif)", "actif"),
    5: ("Trésorerie", "actif"),
}


@dataclass
class CalculerBilan:
    """Bilan simplifié à une date de clôture (soldes cumulés depuis l'origine)."""
    repo: GrandLivreRepository

    async def execute(self, tenant_id: UUID, date_cloture: date) -> list[PosteBilan]:
        lignes = await self.repo.list_by_tenant(tenant_id, None, date_cloture)
        soldes: dict[int, Decimal] = {c: Decimal("0") for c in _BILAN_CLASSES}
        for lg in lignes:
            if not lg.compte_num:
                continue
            cl = int(lg.compte_num[0]) if lg.compte_num[0].isdigit() else 0
            if cl not in soldes:
                continue
            soldes[cl] += lg.debit - lg.credit
        postes = []
        for cl, (libelle, side) in _BILAN_CLASSES.items():
            montant = soldes[cl]
            # classes passif: solde créditeur = positif côté passif
            if side == "passif":
                montant = -montant
            postes.append(PosteBilan(classe=cl, libelle=libelle, montant=montant, side=side))
        return postes


@dataclass
class PosteResultat:
    classe: int
    libelle: str
    montant: Decimal
    nature: str  # "charge" | "produit"


@dataclass
class CalculerResultat:
    """Compte de résultat sur une période (classes 6 et 7)."""
    repo: GrandLivreRepository

    async def execute(
        self, tenant_id: UUID, date_debut: date, date_fin: date
    ) -> tuple[list[PosteResultat], Decimal]:
        lignes = await self.repo.list_by_tenant(tenant_id, date_debut, date_fin)
        charges = Decimal("0")
        produits = Decimal("0")
        for lg in lignes:
            if not lg.compte_num:
                continue
            cl = lg.compte_num[0]
            if cl == "6":
                charges += lg.debit - lg.credit
            elif cl == "7":
                produits += lg.credit - lg.debit
        resultat = produits - charges
        postes = [
            PosteResultat(classe=6, libelle="Charges d'exploitation", montant=charges, nature="charge"),
            PosteResultat(classe=7, libelle="Produits d'exploitation", montant=produits, nature="produit"),
        ]
        return postes, resultat
