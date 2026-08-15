#!/usr/bin/env python3
"""Local evaluation harness for the PCG categorization brick (spec: docs/superpowers/specs/
2026-08-15-pcg-categorization-design.md, "Niveau 4"). Not part of the pytest suite.

Replays one or more real FEC exports (Fichier des Écritures Comptables — the official French
accounting export format) against CategorizeEcriture and reports exact top-1 accuracy: for each
class-6 (charges) line, does the predicted compte_code match the real CompteNum, compared at the
6-digit PCG root (CompteNum is zero-padded to 8 digits in real exports; comptes_pcg stores the
6-digit root — see spec §Contexte)?

Requires a local Postgres with migrations applied (comptes_pcg must be seeded):
    docker compose up -d postgres
    uv run alembic upgrade head

Usage:
    uv run python scripts/eval_categorization.py /path/to/FEC20231231.txt [/path/to/FEC20221231.txt ...]

FEC files are encoded ISO-8859-1 (Latin-1) per common export convention, not UTF-8. Input files
must never be committed to the repo.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from comptis.application.categorization.use_cases import CategorizeEcriture
from comptis.domain.categorization.entities import CategorizationPattern, EcritureACategoriser
from comptis.infrastructure.categorization.rapidfuzz_retriever import RapidFuzzAccountRetriever

_PCG_ROOT_LENGTH = 6  # comptes_pcg stores 6-digit roots; real CompteNum is 8-digit zero-padded


class _NullPatternRepo:
    """Always misses. This harness measures the phase-1 RAG fallback baseline alone — there is
    no learned tenant history yet on a first run, and seeding one from this same file would make
    the harness grade its own homework."""

    async def find_by_libelle(self, tenant_id, libelle_pattern) -> CategorizationPattern | None:
        return None

    async def upsert(self, pattern: CategorizationPattern) -> CategorizationPattern:
        return pattern


class _NullDecisionRepo:
    async def save(self, decision) -> None:
        return None

    async def get_by_ecriture(self, ecriture_id):
        return None


@dataclass
class _Row:
    libelle: str
    compte_num: str
    montant: Decimal
    ecriture_date: date


def _parse_amount(raw: str) -> Decimal:
    if not raw:
        return Decimal("0")
    try:
        return Decimal(raw.replace(",", "."))
    except InvalidOperation:
        return Decimal("0")


def _parse_fec_date(raw: str | None) -> date:
    # FEC standard is YYYYMMDD; fall back to today() for missing/malformed dates rather than
    # crash a multi-thousand-row replay over one bad cell. csv.DictReader fills a field with
    # None (its restval default) when a physical row has fewer columns than the header, so the
    # None-guard below matters as much as the ValueError catch for a malformed string.
    if not raw:
        return date.today()
    try:
        return datetime.strptime(raw.strip(), "%Y%m%d").date()
    except ValueError:
        return date.today()


def _read_rows(path: str) -> list[_Row]:
    rows: list[_Row] = []
    with open(path, encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        required = {"CompteNum", "EcritureLib", "Debit", "EcritureDate"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise SystemExit(
                f"Expected FEC columns {required} in {path}, found: {reader.fieldnames}"
            )
        for raw in reader:
            compte_num = (raw["CompteNum"] or "").strip()
            libelle = (raw["EcritureLib"] or "").strip()
            if not compte_num.startswith("6") or not libelle:
                continue  # scope: class-6 (charges) accounts only, matching the seeded comptes_pcg
            rows.append(_Row(
                libelle=libelle,
                compte_num=compte_num,
                montant=_parse_amount(raw["Debit"]),
                ecriture_date=_parse_fec_date(raw["EcritureDate"]),
            ))
    return rows


async def _run(paths: list[str]) -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            retriever = await RapidFuzzAccountRetriever.load(session)

    use_case = CategorizeEcriture(
        pattern_repo=_NullPatternRepo(),
        account_retriever=retriever,
        decision_repo=_NullDecisionRepo(),
    )

    rows: list[_Row] = []
    for path in paths:
        rows.extend(_read_rows(path))

    correct = 0
    escalated = 0
    correct_and_auto_validated = 0
    print(f"{'libellé écriture':<45} | {'CompteNum réel':<14} | {'prédit':<10} | {'conf.':<6} | statut | exact?")
    print("-" * 110)
    for row in rows:
        ecriture = EcritureACategoriser(
            id=uuid4(), libelle=row.libelle, montant=row.montant, tiers=row.libelle,
            date=row.ecriture_date,
        )
        decision = await use_case.execute(tenant_id=uuid4(), ecriture=ecriture)
        real_root = row.compte_num[:_PCG_ROOT_LENGTH]
        is_exact = decision.compte_code == real_root
        correct += int(is_exact)
        is_escalated = decision.statut.value == "pending_review"
        escalated += int(is_escalated)
        if is_exact and not is_escalated:
            correct_and_auto_validated += 1
        print(
            f"{row.libelle[:45]:<45} | {row.compte_num:<14} | {decision.compte_code:<10} | "
            f"{decision.confidence:<6.2f} | {decision.statut.value:<14} | {'oui' if is_exact else 'non'}"
        )

    total = len(rows)
    print("-" * 110)
    print(f"Total lignes évaluées (classe 6 uniquement) : {total}")
    if total:
        print(f"Précision top-1 (racine PCG 6 chiffres) : {correct}/{total} ({100 * correct / total:.1f}%)")
        print(f"Escaladées en Human Review : {escalated}/{total} ({100 * escalated / total:.1f}%)")
        print(
            f"Correctes ET auto-validées (sans revue humaine) : "
            f"{correct_and_auto_validated}/{total} ({100 * correct_and_auto_validated / total:.1f}%)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fec_paths", nargs="+", help="One or more local FEC export paths (never committed)")
    args = parser.parse_args()
    asyncio.run(_run(args.fec_paths))


if __name__ == "__main__":
    main()
