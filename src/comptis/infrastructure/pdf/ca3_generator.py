"""Génère le formulaire CA3 (N°3310-CA3-SD) en PDF avec fpdf2."""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fpdf import FPDF


@dataclass
class CA3Data:
    raison_sociale: str
    adresse: str
    code_postal_ville: str
    siret: str
    tva_intracomm: str
    periode_debut: date
    periode_fin: date

    a1_ventes: Decimal = Decimal("0")
    a2_autres_imposables: Decimal = Decimal("0")

    b08_base_20: Decimal = Decimal("0")
    b08_taxe_20: Decimal = Decimal("0")
    b9b_base_10: Decimal = Decimal("0")
    b9b_taxe_10: Decimal = Decimal("0")
    b09_base_55: Decimal = Decimal("0")
    b09_taxe_55: Decimal = Decimal("0")

    ded_19_immos: Decimal = Decimal("0")
    ded_20_autres: Decimal = Decimal("0")
    ded_22_report: Decimal = Decimal("0")

    @property
    def total_taxe_brute(self) -> Decimal:
        return self.b08_taxe_20 + self.b9b_taxe_10 + self.b09_taxe_55

    @property
    def total_deductible(self) -> Decimal:
        return self.ded_19_immos + self.ded_20_autres + self.ded_22_report

    @property
    def credit_tva(self) -> Decimal:
        return max(Decimal("0"), self.total_deductible - self.total_taxe_brute)

    @property
    def tva_due(self) -> Decimal:
        return max(Decimal("0"), self.total_taxe_brute - self.total_deductible)


def _round_tva(val: Decimal) -> int:
    """Arrondit selon règle DGFiP : ≥ 0,50 → 1."""
    return int(val.quantize(Decimal("1"), rounding="ROUND_HALF_UP"))


def _fmt(val: Decimal) -> str:
    if val == Decimal("0"):
        return ""
    n = _round_tva(val)
    return f"{n:,}".replace(",", " ")  # narrow no-break space


def _fmt_ht(val: Decimal) -> str:
    return _fmt(val)


# ── Colors ────────────────────────────────────────────────────────────────────

BLUE = (0, 52, 138)        # GOV_BLUE #00348A
LIGHT_BLUE = (232, 239, 248)
FILLED = (255, 253, 231)   # yellow tint
FILLED_GREEN = (232, 245, 233)
DARK_GREEN = (27, 94, 32)
MUTED = (85, 85, 85)
BORDER = (44, 44, 44)
LIGHT_BORDER = (136, 136, 136)
WHITE = (255, 255, 255)
TEXT = (10, 10, 10)


class CA3PDF(FPDF):
    def __init__(self, data: CA3Data):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.data = data
        self.set_margins(15, 10, 15)
        self.set_auto_page_break(auto=False)
        self.core_fonts_encoding = "cp1252"  # includes € sign

    # ── Helpers ───────────────────────────────────────────────────────────────

    def set_color(self, rgb: tuple, fill: bool = False, draw: bool = False):
        r, g, b = rgb
        if fill:
            self.set_fill_color(r, g, b)
        if draw:
            self.set_draw_color(r, g, b)
        if not fill and not draw:
            self.set_text_color(r, g, b)

    def band(self, h: float, color: tuple, y: float | None = None) -> None:
        if y is not None:
            self.set_y(y)
        self.set_color(color, fill=True)
        self.set_color(color, draw=True)
        self.rect(self.l_margin, self.get_y(), self.epw, h, style="F")

    def hline(self, color: tuple = LIGHT_BORDER, lw: float = 0.2) -> None:
        self.set_draw_color(*color)
        self.set_line_width(lw)
        self.line(self.l_margin, self.get_y(), self.l_margin + self.epw, self.get_y())

    def section_header(self, letter: str, title: str) -> None:
        y = self.get_y()
        h = 7
        self.set_fill_color(*BLUE)
        self.rect(self.l_margin, y, self.epw, h, style="F")
        self.set_y(y)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*WHITE)
        self.set_x(self.l_margin + 2)
        self.cell(8, h, letter, align="C")
        self.set_font("Helvetica", "B", 8)
        self.cell(0, h, title)
        self.ln(h)

    def col_header(self, cols: list[tuple[str, float, str]]) -> None:
        """cols = [(label, width, align), ...]"""
        y = self.get_y()
        h = 5.5
        self.set_fill_color(*LIGHT_BLUE)
        self.rect(self.l_margin, y, self.epw, h, style="F")
        self.set_y(y)
        self.set_font("Helvetica", "B", 6.5)
        self.set_text_color(*BLUE)
        self.set_x(self.l_margin)
        for label, w, align in cols:
            self.cell(w, h, label, align=align)
        self.ln(h)
        self.hline(BORDER, 0.4)

    def data_row(
        self,
        desc: str,
        code: str,
        amount: str,
        row_h: float = 6.5,
        filled: bool = False,
        filled_rgb: tuple = FILLED,
        bold: bool = False,
        row_bg: tuple | None = None,
        sub: str = "",
        code_w: float = 12,
        amount_w: float = 28,
    ) -> None:
        desc_w = self.epw - code_w - amount_w
        y = self.get_y()

        if row_bg:
            self.set_fill_color(*row_bg)
            self.rect(self.l_margin, y, self.epw, row_h, style="F")

        if filled and amount:
            ax = self.l_margin + desc_w + code_w
            self.set_fill_color(*filled_rgb)
            self.rect(ax, y, amount_w, row_h, style="F")

        # Description
        self.set_xy(self.l_margin + 1.5, y + (row_h - 4) / 2)
        self.set_font("Helvetica", "B" if bold else "", 7.5)
        self.set_text_color(*TEXT)
        self.cell(desc_w - 1.5, 4, desc, align="L")

        if sub:
            self.set_xy(self.l_margin + 1.5, y + row_h - 2.5)
            self.set_font("Helvetica", "", 5.5)
            self.set_text_color(*MUTED)
            self.cell(desc_w - 1.5, 2.5, sub, align="L")

        # Code
        self.set_xy(self.l_margin + desc_w, y + (row_h - 4) / 2)
        self.set_font("Helvetica", "", 6.5)
        self.set_text_color(*MUTED)
        self.cell(code_w, 4, code, align="C")

        # Amount
        self.set_xy(self.l_margin + desc_w + code_w, y + (row_h - 4) / 2)
        self.set_font("Helvetica", "B" if (bold or amount) else "", 8)
        self.set_text_color(*(DARK_GREEN if filled and filled_rgb == FILLED_GREEN else TEXT))
        self.cell(amount_w - 1.5, 4, amount, align="R")

        # Borders
        self.set_y(y + row_h)
        self.hline()
        self.set_draw_color(*LIGHT_BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin + desc_w, y, self.l_margin + desc_w, y + row_h)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.5)
        self.line(self.l_margin + desc_w + code_w, y, self.l_margin + desc_w + code_w, y + row_h)

    def data_row2(
        self,
        desc: str,
        code: str,
        base: str,
        taxe: str,
        row_h: float = 6.5,
        filled: bool = False,
        code_w: float = 12,
        amount_w: float = 28,
    ) -> None:
        desc_w = self.epw - code_w - amount_w * 2
        y = self.get_y()

        if filled and taxe:
            ax = self.l_margin + desc_w + code_w + amount_w
            self.set_fill_color(*FILLED)
            self.rect(ax, y, amount_w, row_h, style="F")

        self.set_xy(self.l_margin + 1.5, y + (row_h - 4) / 2)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*TEXT)
        self.cell(desc_w - 1.5, 4, desc)

        self.set_xy(self.l_margin + desc_w, y + (row_h - 4) / 2)
        self.set_font("Helvetica", "", 6.5)
        self.set_text_color(*MUTED)
        self.cell(code_w, 4, code, align="C")

        # Base HT
        self.set_xy(self.l_margin + desc_w + code_w, y + (row_h - 4) / 2)
        self.set_font("Helvetica", "B" if base else "", 7.5)
        self.set_text_color(*MUTED)
        self.cell(amount_w - 1, 4, base, align="R")

        # Taxe due
        self.set_xy(self.l_margin + desc_w + code_w + amount_w, y + (row_h - 4) / 2)
        self.set_font("Helvetica", "B" if taxe else "", 8)
        self.set_text_color(*TEXT)
        self.cell(amount_w - 1.5, 4, taxe, align="R")

        self.set_y(y + row_h)
        self.hline()
        for dx in [desc_w, desc_w + code_w, desc_w + code_w + amount_w]:
            lw = 0.5 if dx == desc_w + code_w else 0.2
            self.set_draw_color(*BORDER)
            self.set_line_width(lw)
            self.line(self.l_margin + dx, y, self.l_margin + dx, y + row_h)

    def outer_border(self) -> None:
        self.set_draw_color(*BORDER)
        self.set_line_width(1.0)
        self.rect(self.l_margin, 8, self.epw, self.h - 18, style="D")

    def page_header_band(self, page: str) -> None:
        d = self.data
        h = 6
        y = self.get_y()
        self.set_fill_color(*BLUE)
        self.rect(self.l_margin, y, self.epw, h, style="F")
        self.set_y(y)
        self.set_x(self.l_margin + 2)
        self.set_font("Helvetica", "B", 7.5)
        self.set_text_color(*WHITE)
        self.cell(35, h, "N° 3310-CA3-SD")
        period = f"{d.periode_debut.strftime('%d/%m/%Y')} - {d.periode_fin.strftime('%d/%m/%Y')}"
        self.set_font("Helvetica", "", 7.5)
        self.cell(self.epw - 35 - 20, h, f"{d.raison_sociale}  |  {period}", align="C")
        self.cell(20, h, page, align="R")
        self.ln(h)


# ── Pages ─────────────────────────────────────────────────────────────────────

def _page1(pdf: CA3PDF) -> None:
    d = pdf.data
    pdf.add_page()

    # Top band
    pdf.set_y(10)
    h = 10
    pdf.set_fill_color(*BLUE)
    pdf.rect(pdf.l_margin, pdf.get_y(), pdf.epw, h, style="F")
    pdf.set_y(pdf.get_y() + 1.5)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*WHITE)
    pdf.cell(pdf.epw, 4, "TAXE SUR LA VALEUR AJOUTÉE ET TAXES ASSIMILÉES", align="C")
    pdf.ln(4)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.cell(pdf.epw, 3, "RÉGIME DU RÉEL NORMAL  -  MENSUEL (EM)", align="C")
    pdf.set_y(pdf.get_y() + h - 7.5 + 10)

    # Refs bar
    h_ref = 7
    y = pdf.get_y()
    pdf.set_fill_color(*LIGHT_BLUE)
    pdf.rect(pdf.l_margin, y, pdf.epw, h_ref, style="F")
    pdf.set_y(y + 1.5)
    pdf.set_x(pdf.l_margin + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*BLUE)
    pdf.cell(30, 4, "N° 3310-CA3-SD")
    pdf.cell(25, 4, "N° 10963*31")
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*MUTED)
    pdf.cell(60, 4, "MODÈLE OBLIGATOIRE (art. 287 du CGI)")
    pdf.set_x(pdf.l_margin + pdf.epw - 45)
    pdf.cell(45, 4, "Généré par Comptis", align="R")
    pdf.set_y(y + h_ref)

    # Period box
    y = pdf.get_y()
    box_h = 10
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.8)
    pdf.rect(pdf.l_margin, y, pdf.epw, box_h, style="D")
    mid_y = y + box_h / 2 - 2
    pdf.set_xy(pdf.l_margin + 2, mid_y)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*TEXT)
    pdf.cell(52, 4, "PÉRIODE DE DÉCLARATION")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(6, 4, "Du")
    # debut box
    pdf.set_fill_color(*FILLED)
    pdf.rect(pdf.get_x(), y + 2, 30, 6, style="F")
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.4)
    pdf.rect(pdf.get_x(), y + 2, 30, 6, style="D")
    pdf.set_font("Helvetica", "B", 9)
    x_box = pdf.get_x()
    pdf.set_xy(x_box + 1, y + 3.5)
    pdf.cell(28, 4, d.periode_debut.strftime("%d/%m/%Y"), align="C")
    pdf.set_x(x_box + 32)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(6, 4, "au", align="C")
    # fin box
    pdf.set_fill_color(*FILLED)
    x2 = pdf.get_x()
    pdf.rect(x2, y + 2, 30, 6, style="F")
    pdf.set_draw_color(*BORDER)
    pdf.rect(x2, y + 2, 30, 6, style="D")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(x2 + 1, y + 3.5)
    pdf.cell(28, 4, d.periode_fin.strftime("%d/%m/%Y"), align="C")
    pdf.set_y(y + box_h)

    # Identification
    id_h = 38
    y = pdf.get_y()
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.8)
    pdf.rect(pdf.l_margin, y, pdf.epw, id_h, style="D")

    pdf.set_xy(pdf.l_margin + 2, y + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 4, "Identification du redevable")

    pdf.set_xy(pdf.l_margin + 2, y + 7)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(40, 3, "Nom ou dénomination")

    pdf.set_xy(pdf.l_margin + 2, y + 11)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*TEXT)
    pdf.cell(0, 5, d.raison_sociale)

    pdf.set_xy(pdf.l_margin + 2, y + 18)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(20, 3, "Adresse")

    pdf.set_xy(pdf.l_margin + 2, y + 22)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*TEXT)
    pdf.cell(0, 4, d.adresse)

    pdf.set_xy(pdf.l_margin + 2, y + 27)
    pdf.cell(0, 4, d.code_postal_ville)

    pdf.set_y(y + id_h)

    # SIRET + TVA row
    siret_h = 17
    y = pdf.get_y()
    mid = pdf.epw / 2
    pdf.set_draw_color(*BORDER)
    pdf.rect(pdf.l_margin, y, pdf.epw, siret_h, style="D")
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin + mid, y, pdf.l_margin + mid, y + siret_h)

    # SIRET
    pdf.set_xy(pdf.l_margin + 2, y + 2)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(mid - 2, 3, "N° d'identification de l'établissement (SIRET)")

    pdf.set_fill_color(*FILLED)
    pdf.set_draw_color(*BORDER)
    pdf.rect(pdf.l_margin + 2, y + 6, mid - 4, 7, style="FD")
    pdf.set_xy(pdf.l_margin + 2, y + 7.5)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*TEXT)
    pdf.cell(mid - 4, 4, d.siret, align="C")

    # TVA intracomm
    pdf.set_xy(pdf.l_margin + mid + 2, y + 2)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(mid - 4, 3, "N° TVA intracommunautaire")

    pdf.set_fill_color(*FILLED)
    pdf.set_draw_color(*BORDER)
    pdf.rect(pdf.l_margin + mid + 2, y + 6, mid - 4, 7, style="FD")
    pdf.set_xy(pdf.l_margin + mid + 2, y + 7.5)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*TEXT)
    pdf.cell(mid - 4, 4, d.tva_intracomm, align="C")

    pdf.set_y(y + siret_h)

    # Notes
    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, "Régime : EM (réel normal mensuel)  |  Dépôt mensuel obligatoire")
    pdf.ln(3)
    pdf.hline(BORDER, 0.6)
    pdf.ln(4)

    # Case néant
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, "Si aucune ligne à remplir (déclaration néant), cocher la case 0010")
    y_case = pdf.get_y()
    pdf.set_draw_color(*BORDER)
    pdf.rect(pdf.l_margin + pdf.epw - 8, y_case, 5, 5, style="D")
    pdf.ln(10)

    # Signature block
    sig_h = 28
    y = pdf.get_y()
    pdf.set_draw_color(*BORDER)
    pdf.rect(pdf.l_margin, y, pdf.epw, sig_h, style="D")
    mid = pdf.epw / 2
    pdf.line(pdf.l_margin + mid, y, pdf.l_margin + mid, y + sig_h)
    # left
    pdf.set_xy(pdf.l_margin + 2, y + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*BLUE)
    pdf.cell(mid - 2, 4, "PAIEMENT, DATE, SIGNATURE")
    pdf.set_xy(pdf.l_margin + 2, y + 8)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*TEXT)
    pdf.cell(mid - 2, 4, "Date : ____________________________")
    pdf.set_xy(pdf.l_margin + 2, y + 14)
    pdf.cell(mid - 2, 4, "Tél. : _____________________________")
    pdf.set_xy(pdf.l_margin + 2, y + 20)
    pdf.cell(mid - 2, 4, "Signature :")
    # right
    pdf.set_xy(pdf.l_margin + mid + 2, y + 2)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*MUTED)
    pdf.cell(mid - 2, 4, "RÉSERVÉ À L'ADMINISTRATION")

    pdf.set_y(y + sig_h)

    # Footer
    pdf.set_y(pdf.h - 12)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, "N° 3310-CA3-SD  |  N° 10963*31  |  Page 1/3  |  Vous devez déclarer et payer votre TVA sur impots.gouv.fr")
    pdf.outer_border()


def _page2(pdf: CA3PDF) -> None:
    d = pdf.data
    pdf.add_page()
    pdf.set_y(10)
    pdf.page_header_band("Page 2/3")

    pdf.ln(2)
    pdf.section_header("A", "MONTANT DES OPÉRATIONS RÉALISÉES")

    code_w = 12
    amount_w = 28
    pdf.col_header([
        ("Désignation", pdf.epw - code_w - amount_w, "L"),
        ("Code", code_w, "C"),
        ("Montant HT (€)", amount_w, "R"),
    ])

    ops_taxees = [
        ("A1  Ventes et prestations de services", "0979", _fmt_ht(d.a1_ventes)),
        ("A2  Autres opérations imposables", "0981", _fmt_ht(d.a2_autres_imposables)),
        ("A3  Achats de prestations (art. 283-2 CGI)", "0044", ""),
        ("A4  Importations (hors produits pétroliers)", "0056", ""),
        ("A5  Sorties de régime fiscal suspensif", "0051", ""),
        ("B2  Acquisitions intracommunautaires", "0031", ""),
        ("B5  Régularisations", "0036", ""),
    ]
    ops_non_taxees = [
        ("E1  Exportations hors UE", "0032", ""),
        ("E2  Autres opérations non imposables", "0033", ""),
        ("E3  Ventes à distance taxables dans un autre État membre", "0047", ""),
        ("F2  Livraisons intracommunautaires B to B", "0034", ""),
        ("F8  Régularisations", "0039", ""),
    ]

    pdf.data_row("OPÉRATIONS TAXÉES (HT)", "", "", row_bg=LIGHT_BLUE, bold=True)
    for desc, code, amt in ops_taxees:
        pdf.data_row(desc, code, amt, filled=bool(amt))

    pdf.data_row("OPÉRATIONS NON TAXÉES", "", "", row_bg=LIGHT_BLUE, bold=True)
    for desc, code, amt in ops_non_taxees:
        pdf.data_row(desc, code, amt)

    pdf.hline(BORDER, 0.6)
    pdf.ln(3)

    # ── Section B - TVA brute ──────────────────────────────────────────────────
    pdf.section_header("B", "DÉCOMPTE DE LA TVA À PAYER  -  TVA BRUTE")

    desc_w2 = pdf.epw - code_w - amount_w * 2
    pdf.col_header([
        ("Désignation", desc_w2, "L"),
        ("Code", code_w, "C"),
        ("Base HT (€)", amount_w, "R"),
        ("Taxe due (€)", amount_w, "R"),
    ])

    taux_rows = [
        ("08  Taux normal 20 %",          "0207", d.b08_base_20, d.b08_taxe_20),
        ("09  Taux réduit 5,5 %",         "0105", d.b09_base_55, d.b09_taxe_55),
        ("9B  Taux réduit 10 %",          "0151", d.b9b_base_10, d.b9b_taxe_10),
        ("9C  Taux particuliers (2,1 %)", "0900", Decimal("0"), Decimal("0")),
        ("10  Acquisitions intracomm.",    "0031", Decimal("0"), Decimal("0")),
        ("11  Importations",              "0056", Decimal("0"), Decimal("0")),
        ("3B  Autres opérations",         "0040", Decimal("0"), Decimal("0")),
        ("5B  Régularisations",           "0036", Decimal("0"), Decimal("0")),
    ]
    for desc, code, base, taxe in taux_rows:
        pdf.data_row2(desc, code, _fmt_ht(base), _fmt(taxe), filled=base > 0 or taxe > 0)

    # Ligne 16 total
    y16 = pdf.get_y()
    row_h = 7
    pdf.set_fill_color(*LIGHT_BLUE)
    pdf.rect(pdf.l_margin, y16, pdf.epw, row_h, style="F")
    if d.total_taxe_brute > 0:
        pdf.set_fill_color(*FILLED)
        pdf.rect(pdf.l_margin + desc_w2 + code_w + amount_w, y16, amount_w, row_h, style="F")
    pdf.set_xy(pdf.l_margin + 1.5, y16 + 1.5)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*TEXT)
    pdf.cell(desc_w2 - 1.5, 4, "16   Total de la TVA brute due (lignes 08 à 5B)")
    pdf.set_xy(pdf.l_margin + desc_w2, y16 + 1.5)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(code_w, 4, "0600", align="C")
    pdf.set_xy(pdf.l_margin + desc_w2 + code_w + amount_w, y16 + 1.5)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*TEXT)
    pdf.cell(amount_w - 1.5, 4, _fmt(d.total_taxe_brute) or "0", align="R")
    pdf.set_y(y16 + row_h)
    pdf.hline(BORDER, 0.6)

    # Footer
    pdf.set_y(pdf.h - 12)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, "N° 3310-CA3-SD  |  N° 10963*31  |  Page 2/3")
    pdf.outer_border()


def _page3(pdf: CA3PDF) -> None:
    d = pdf.data
    pdf.add_page()
    pdf.set_y(10)
    pdf.page_header_band("Page 3/3")

    # Reminder line 16
    pdf.ln(1)
    pdf.set_x(pdf.l_margin)
    total_str = _fmt(d.total_taxe_brute) or "0"
    pdf.set_fill_color(*LIGHT_BLUE)
    pdf.rect(pdf.l_margin, pdf.get_y(), pdf.epw, 6, style="F")
    pdf.set_y(pdf.get_y() + 1)
    pdf.set_x(pdf.l_margin + 2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 4, f"Ligne 16  -  Total TVA brute due : {total_str} €")
    pdf.ln(6)

    # ── TVA déductible ─────────────────────────────────────────────────────────
    pdf.section_header("C", "TVA DÉDUCTIBLE")

    code_w = 12
    amount_w = 28

    pdf.col_header([
        ("Désignation", pdf.epw - code_w - amount_w, "L"),
        ("Code", code_w, "C"),
        ("TVA déductible (€)", amount_w, "R"),
    ])

    ded_rows = [
        ("19   Biens constituant des immobilisations", "0703", d.ded_19_immos, False),
        ("20   Autres biens et services", "0702", d.ded_20_autres, True),
        ("21   Autre TVA à déduire", "0059", Decimal("0"), False),
        ("22   Report du crédit (ligne 27 décl. précédente)", "8001", d.ded_22_report, bool(d.ded_22_report)),
        ("2C  Sommes à imputer (y compris acomptes)", "0603", Decimal("0"), False),
    ]
    for desc, code, val, has_sub in ded_rows:
        sub = "Achats courants, frais généraux - factures vérifiées et rapprochées" if has_sub else ""
        pdf.data_row(desc, code, _fmt(val), filled=val > 0, sub=sub)

    # Ligne 23 total
    y23 = pdf.get_y()
    row_h = 7
    pdf.set_fill_color(*LIGHT_BLUE)
    pdf.rect(pdf.l_margin, y23, pdf.epw, row_h, style="F")
    if d.total_deductible > 0:
        pdf.set_fill_color(*FILLED)
        pdf.rect(pdf.l_margin + pdf.epw - code_w - amount_w, y23, amount_w, row_h, style="F")
    pdf.set_xy(pdf.l_margin + 1.5, y23 + 1.5)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*TEXT)
    pdf.cell(pdf.epw - code_w - amount_w - 1.5, 4, "23   Total TVA déductible (lignes 19 à 2C)")
    pdf.set_xy(pdf.l_margin + pdf.epw - code_w - amount_w, y23 + 1.5)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(code_w, 4, "0705", align="C")
    pdf.set_xy(pdf.l_margin + pdf.epw - amount_w, y23 + 1.5)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*TEXT)
    pdf.cell(amount_w - 1.5, 4, _fmt(d.total_deductible) or "0", align="R")
    pdf.set_y(y23 + row_h)
    pdf.hline(BORDER, 0.6)
    pdf.ln(3)

    # ── TVA due / crédit ───────────────────────────────────────────────────────
    pdf.section_header("D", "TVA DUE OU CRÉDIT DE TVA")
    pdf.col_header([
        ("Désignation", pdf.epw - code_w - amount_w, "L"),
        ("Code", code_w, "C"),
        ("Montant (€)", amount_w, "R"),
    ])

    if d.credit_tva > 0:
        pdf.data_row(
            "25   Crédit de TVA  (ligne 23 - ligne 16)",
            "0705",
            _fmt(d.credit_tva),
            filled=True,
            filled_rgb=FILLED_GREEN,
            bold=True,
            sub=f"Excédent déductible : {_fmt(d.total_deductible)} - {_fmt(d.total_taxe_brute) or '0'} = {_fmt(d.credit_tva)} €",
        )
    else:
        pdf.data_row("25   Crédit de TVA  (ligne 23 - ligne 16)", "0705", "")

    if d.tva_due > 0:
        pdf.data_row("TD  TVA due  (ligne 16 - ligne 23)", "8900", _fmt(d.tva_due),
                     filled=True, bold=True)
    else:
        pdf.data_row("TD  TVA due  (ligne 16 - ligne 23)", "8900", "")

    pdf.ln(3)

    # ── Report crédit ─────────────────────────────────────────────────────────
    pdf.section_header("E", "REMBOURSEMENT / REPORT DU CRÉDIT")
    pdf.col_header([
        ("Désignation", pdf.epw - code_w - amount_w, "L"),
        ("Code", code_w, "C"),
        ("Montant (€)", amount_w, "R"),
    ])

    pdf.data_row("26   Remboursement de crédit demandé", "8002", "")
    pdf.data_row(
        "27   Crédit à reporter sur la prochaine déclaration",
        "8003",
        _fmt(d.credit_tva) if d.credit_tva > 0 else "",
        filled=d.credit_tva > 0,
        filled_rgb=FILLED_GREEN,
        bold=True,
    )
    pdf.hline(BORDER, 0.6)
    pdf.ln(4)

    # ── Result summary ─────────────────────────────────────────────────────────
    is_credit = d.credit_tva > 0
    amount = d.credit_tva if is_credit else d.tva_due
    label = "CRÉDIT DE TVA À REPORTER" if is_credit else "TVA NETTE À PAYER"
    fill_rgb = FILLED_GREEN if is_credit else FILLED
    text_rgb = DARK_GREEN if is_credit else TEXT

    y_res = pdf.get_y()
    res_h = 22
    pdf.set_fill_color(*fill_rgb)
    pdf.set_draw_color(*(27, 126, 32) if is_credit else BORDER)
    pdf.set_line_width(1.0)
    pdf.rect(pdf.l_margin, y_res, pdf.epw, res_h, style="FD")

    pdf.set_xy(pdf.l_margin + 4, y_res + 3)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*text_rgb)
    pdf.cell(pdf.epw - 60, 5, label)

    pdf.set_xy(pdf.l_margin + 4, y_res + 9)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    period_str = f"{d.periode_debut.strftime('%d/%m/%Y')} - {d.periode_fin.strftime('%d/%m/%Y')}"
    pdf.cell(pdf.epw - 60, 4, f"Période : {period_str}")

    pdf.set_xy(pdf.l_margin + 4, y_res + 14)
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(pdf.epw - 60, 3.5,
             f"TVA brute : {_fmt(d.total_taxe_brute) or '0'} €    TVA déductible : {_fmt(d.total_deductible)} €")

    pdf.set_xy(pdf.l_margin + pdf.epw - 58, y_res + 4)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*text_rgb)
    pdf.cell(56, 14, f"{_fmt(amount)} €", align="R")

    pdf.set_y(y_res + res_h + 4)

    # Signature
    sig_h = 26
    y_sig = pdf.get_y()
    pdf.set_draw_color(*LIGHT_BORDER)
    pdf.set_line_width(0.5)
    mid = pdf.epw / 2
    pdf.rect(pdf.l_margin, y_sig, pdf.epw, sig_h, style="D")
    pdf.line(pdf.l_margin + mid, y_sig, pdf.l_margin + mid, y_sig + sig_h)

    pdf.set_xy(pdf.l_margin + 2, y_sig + 2)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*TEXT)
    pdf.cell(mid - 2, 4, "Certification du redevable")
    pdf.set_xy(pdf.l_margin + 2, y_sig + 7)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(mid - 2, 4, "Je certifie que cette déclaration est sincère et complète.")
    pdf.set_xy(pdf.l_margin + 2, y_sig + 13)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*TEXT)
    pdf.cell(mid - 2, 4, "Fait à _________________, le ____/____/2026")
    pdf.line(pdf.l_margin + 2, y_sig + sig_h - 4, pdf.l_margin + mid - 2, y_sig + sig_h - 4)
    pdf.set_xy(pdf.l_margin + 2, y_sig + sig_h - 3)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(mid - 2, 3, "Signature et cachet")

    pdf.set_xy(pdf.l_margin + mid + 2, y_sig + 2)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*BLUE)
    pdf.cell(mid - 4, 4, "Généré par Comptis")
    pdf.set_xy(pdf.l_margin + mid + 2, y_sig + 7)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*MUTED)
    pdf.cell(mid - 4, 4, "Données PNICompta | factures vérifiées et rapprochées")
    pdf.set_xy(pdf.l_margin + mid + 2, y_sig + 12)
    pdf.cell(mid - 4, 4, f"Montant exact avant arrondi : {float(amount):.2f} €")

    # Footer
    pdf.set_y(pdf.h - 12)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, "N° 3310-CA3-SD  |  N° 10963*31  |  Page 3/3")
    pdf.outer_border()


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_ca3(data: CA3Data) -> bytes:
    pdf = CA3PDF(data)
    _page1(pdf)
    _page2(pdf)
    _page3(pdf)
    return pdf.output()
