"""CA3 PDF overlay: fills the official DGFiP template with computed values."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from pypdf import PdfReader, PdfWriter

TEMPLATE_PATH = Path(__file__).parents[4] / "TVA_exemplaire.pdf"

_PAGE_H = 841.9  # A4 height in PDF points
_MM = 25.4 / 72  # pts → mm


def _to_mm(x_pts: float, y_pts: float) -> tuple[float, float]:
    """PDF coords (origin bottom-left) → fpdf2 mm (origin top-left)."""
    return x_pts * _MM, (_PAGE_H - y_pts) * _MM


@dataclass
class CA3OverlayData:
    # Page 1
    periode_debut: date = field(default_factory=date.today)
    periode_fin: date = field(default_factory=date.today)
    raison_sociale: str = ""
    adresse: str = ""
    code_postal_ville: str = ""
    siret: str = ""
    numero_tva: str = ""
    # Page 2 – TVA brute
    a1_ventes: Decimal = Decimal(0)
    l08_base: Decimal = Decimal(0)
    l08_taxe: Decimal = Decimal(0)
    l09_base: Decimal = Decimal(0)
    l09_taxe: Decimal = Decimal(0)
    l9b_base: Decimal = Decimal(0)
    l9b_taxe: Decimal = Decimal(0)
    l16_brute: Decimal = Decimal(0)
    # Page 3 – TVA déductible + résultat
    l19_immos: Decimal = Decimal(0)
    l20_autres: Decimal = Decimal(0)
    l22_report: Decimal = Decimal(0)
    l23_total_ded: Decimal = Decimal(0)
    tva_due: Decimal = Decimal(0)
    credit_tva: Decimal = Decimal(0)


class _OverlayPDF(FPDF):
    core_fonts_encoding = "cp1252"


def _fmt(v: Decimal) -> str:
    return str(int(round(float(v)))) if v else ""


def _fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _build_overlay(page_num: int, data: CA3OverlayData) -> bytes:
    pdf = _OverlayPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(0, 0, 0)
    pdf.add_page()
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(0, 0, 0)

    def ew(x_pts: float, y_pts: float, text: str,
           w_pts: float = 68, h_pts: float = 7, align: str = "R") -> None:
        """Erase ……… area and write value."""
        if not text:
            return
        x_mm, y_mm = _to_mm(x_pts, y_pts)
        w_mm, h_mm = w_pts * _MM, h_pts * _MM
        # white erase
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x_mm - 1, y_mm - h_mm + 1.2, w_mm + 2, h_mm, style="F")
        pdf.set_xy(x_mm - 1, y_mm - h_mm + 1.5)
        pdf.cell(w_mm + 2, h_mm - 1, text, align=align)

    if page_num == 0:
        _page1(pdf, ew, data)
    elif page_num == 1:
        _page2(ew, data)
    elif page_num == 2:
        _page3(ew, data)

    return bytes(pdf.output())


def _page1(pdf: _OverlayPDF, ew, data: CA3OverlayData) -> None:
    # Dates – "Du" text at y=741.1; date boxes right after
    x_du, y_date = _to_mm(183, 741.1)
    x_au, _ = _to_mm(322, 741.1)
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(x_du - 1, y_date - 3, 32, 4.5, style="F")
    pdf.rect(x_au - 1, y_date - 3, 32, 4.5, style="F")
    pdf.set_xy(x_du - 1, y_date - 3)
    pdf.cell(32, 4, _fmt_date(data.periode_debut))
    pdf.set_xy(x_au - 1, y_date - 3)
    pdf.cell(32, 4, _fmt_date(data.periode_fin))

    # Nom ou dénomination – erase from x=130 (before "N" of label) to cover full cell
    if data.raison_sociale:
        x_mm, y_mm = _to_mm(130, 656.8)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x_mm, y_mm - 3.5, 100, 5.5, style="F")
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_xy(x_mm + 1, y_mm - 3)
        pdf.cell(98, 5, data.raison_sociale[:50])
        pdf.set_font("Helvetica", size=8)

    # Adresse
    if data.adresse:
        x_mm, y_mm = _to_mm(130, 615.8)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x_mm, y_mm - 3.5, 100, 5.5, style="F")
        pdf.set_xy(x_mm + 1, y_mm - 3)
        pdf.cell(98, 5, data.adresse[:55])

    if data.code_postal_ville:
        x_mm, y_mm = _to_mm(130, 603.5)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x_mm, y_mm - 3.5, 100, 5.5, style="F")
        pdf.set_xy(x_mm + 1, y_mm - 3)
        pdf.cell(98, 5, data.code_postal_ville[:25])

    # SIRET – boxes at y=524.8, x=240.8
    if data.siret:
        siret = data.siret.replace(" ", "").replace("-", "")[:14]
        x_mm, y_mm = _to_mm(240.8, 524.8)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x_mm - 1, y_mm - 3.2, 115, 5, style="F")
        pdf.set_font("Courier", size=8)
        pdf.set_xy(x_mm, y_mm - 2.8)
        spaced = "  ".join(list(siret))
        pdf.cell(115, 4, spaced)
        pdf.set_font("Helvetica", size=8)

    # N° TVA intra – y=510.1, x=240.8
    if data.numero_tva:
        x_mm, y_mm = _to_mm(240.8, 510.1)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x_mm - 1, y_mm - 3.2, 115, 5, style="F")
        pdf.set_xy(x_mm, y_mm - 2.8)
        pdf.cell(115, 4, data.numero_tva[:25])


def _page2(ew, data: CA3OverlayData) -> None:
    # A1 ventes HT (0979) – y=788.3, single right-side value at x=245.4
    ew(245.4, 788.3, _fmt(data.a1_ventes))

    # Ligne 08 Taux 20% (0207) – y=424.7 | base at x=451.3, taxe at x=525.5
    ew(451.3, 424.7, _fmt(data.l08_base))
    ew(525.5, 424.7, _fmt(data.l08_taxe))

    # Ligne 09 Taux 5,5% (0105) – y=410.6
    ew(451.3, 410.6, _fmt(data.l09_base))
    ew(525.5, 410.6, _fmt(data.l09_taxe))

    # Ligne 9B Taux 10% (0151) – y=396.4
    ew(451.3, 396.4, _fmt(data.l9b_base))
    ew(525.5, 396.4, _fmt(data.l9b_taxe))


def _page3(ew, data: CA3OverlayData) -> None:
    # Colonnes droites: les pointillés (…………) commencent à x≈525 mais la
    # cellule se termine à x≈575. On écrase depuis x=505, largeur=70 pour
    # que la valeur reste dans la cellule.
    _R = dict(w_pts=70, h_pts=8)  # right-column params

    # Ligne 16 Total TVA brute – y=818.4
    ew(505, 818.4, _fmt(data.l16_brute), **_R)

    # Ligne 19 immos (0703) – y=764.0
    ew(505, 764.0, _fmt(data.l19_immos), **_R)

    # Ligne 20 autres (0702) – y=750.5
    ew(505, 750.5, _fmt(data.l20_autres), **_R)

    # Ligne 22 report (8001) – y=699.2
    ew(505, 699.2, _fmt(data.l22_report), **_R)

    # Ligne 23 total déductible – y=672.1, encadré |___________|
    ew(505, 672.1, _fmt(data.l23_total_ded), w_pts=70, h_pts=7)

    # TD TVA due (8900) – y=601.0
    ew(505, 601.0, _fmt(data.tva_due), **_R)

    # Ligne 25 Crédit TVA (0705) – y=601.0, colonne gauche x≈242
    ew(222, 601.0, _fmt(data.credit_tva), w_pts=70, h_pts=8)


def fill_ca3(data: CA3OverlayData, template: Path = TEMPLATE_PATH) -> bytes:
    """Fill the official CA3 template with given data, return PDF bytes."""
    reader = PdfReader(str(template))
    writer = PdfWriter()

    for i in range(len(reader.pages)):
        overlay_bytes = _build_overlay(i, data)
        overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
        page = reader.pages[i]
        page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
