from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.comptabilite.entities import Ecriture
from comptis.domain.comptabilite.value_objects import StatutEcriture
from comptis.infrastructure.db.comptabilite_repository import SQLAlchemyEcritureRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.interface.api.dependencies import get_db_session, require_user

router = APIRouter(prefix="/ecritures", tags=["ecritures"])


class EcritureSchema(BaseModel):
    id: uuid.UUID
    transaction_id: str
    facture_id: str
    montant: Decimal
    date: date
    compte_id: uuid.UUID | None
    statut: str
    created_at: str


@router.get("", response_model=list[EcritureSchema])
async def list_ecritures(
    tenant_id: uuid.UUID = Query(...),
    statut: str | None = Query(None),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[EcritureSchema]:
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await set_tenant_context(session, organization_id=tenant.organization_id, tenant_id=tenant_id, user_id=user_id)
    repo = SQLAlchemyEcritureRepository(session)
    ecritures = await repo.list_by_tenant(tenant_id, statut=statut)
    return [
        EcritureSchema(
            id=e.id,
            transaction_id=e.transaction_id,
            facture_id=e.facture_id,
            montant=e.montant,
            date=e.date,
            compte_id=e.compte_id,
            statut=e.statut.value,
            created_at=e.created_at.isoformat(),
        )
        for e in ecritures
    ]


# ── Import relevé bancaire CSV ─────────────────────────────────────────────────

class ImportCSVResponse(BaseModel):
    importees: int
    ignorees: int


def _detect_and_parse(text: str) -> list[dict]:
    """
    Detect CSV format among common French bank exports.
    Returns list of dicts with keys: date (date), libelle (str), montant (Decimal).

    Supported formats (auto-detected by header):
    - BNP Paribas: Date;Libellé;Montant;Devise
    - Crédit Agricole: Date;Libellé court;Libellé complet;Montant;Devise
    - Société Générale: Date;Intitulé;Référence;Date valeur;Montant;Devise
    - Generic (separator sniff): date|libelle/description|montant columns
    """
    # Sniff separator
    sample = text[:2000]
    sep = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=sep)
    headers_raw = reader.fieldnames or []
    headers = [h.strip().lower() for h in headers_raw]

    # Map header to canonical key
    DATE_KEYS = {"date", "date opération", "date operation"}
    LIB_KEYS = {"libellé", "libelle", "intitulé", "intitule", "description",
                "libellé court", "libelle court"}
    AMT_KEYS = {"montant", "amount", "débit/crédit"}

    def find_col(candidates: set[str]) -> str | None:
        for i, h in enumerate(headers):
            if h in candidates:
                return (headers_raw or [])[i]
        return None

    col_date = find_col(DATE_KEYS)
    col_lib = find_col(LIB_KEYS)
    col_amt = find_col(AMT_KEYS)

    if not (col_date and col_lib and col_amt):
        # Fallback: assume first 3 columns are date, libelle, montant
        if len(headers_raw) >= 3:
            col_date, col_lib, col_amt = headers_raw[0], headers_raw[1], headers_raw[2]
        else:
            return []

    rows = []
    for row in reader:
        raw_date = (row.get(col_date) or "").strip()
        raw_lib = (row.get(col_lib) or "").strip()
        raw_amt = (row.get(col_amt) or "").strip().replace(" ", "").replace(" ", "").replace(",", ".")

        # Skip empty rows
        if not raw_date or not raw_lib or not raw_amt:
            continue

        # Parse date (try DD/MM/YYYY then YYYY-MM-DD)
        parsed_date: date | None = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
            try:
                parsed_date = datetime.strptime(raw_date, fmt).date()
                break
            except ValueError:
                continue
        if parsed_date is None:
            continue

        try:
            montant = Decimal(raw_amt)
        except InvalidOperation:
            continue

        rows.append({"date": parsed_date, "libelle": raw_lib, "montant": montant})

    return rows


@router.post("/import-csv", response_model=ImportCSVResponse)
async def import_csv(
    tenant_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImportCSVResponse:
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    await set_tenant_context(session, organization_id=tenant.organization_id,
                             tenant_id=tenant_id, user_id=user_id)

    raw = await file.read()
    # Try UTF-8 with BOM, fallback to latin-1
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    rows = _detect_and_parse(text)
    if not rows:
        raise HTTPException(422, "Format CSV non reconnu ou fichier vide")

    repo = SQLAlchemyEcritureRepository(session)
    importees = ignorees = 0
    for r in rows:
        txn_id = f"CSV-{r['date'].isoformat()}-{abs(hash(r['libelle'] + str(r['montant'])))}"
        e = Ecriture(
            tenant_id=tenant_id,
            transaction_id=txn_id,
            facture_id="",
            montant=r["montant"],
            date=r["date"],
            ecriture_lib=r["libelle"],
            statut=StatutEcriture.A_CATEGORISER,
        )
        try:
            await repo.save(e)
            importees += 1
        except Exception:
            ignorees += 1

    return ImportCSVResponse(importees=importees, ignorees=ignorees)
