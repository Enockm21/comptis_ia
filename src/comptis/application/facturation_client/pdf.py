from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER


@dataclass
class LignePDF:
    description: str
    quantite: Decimal
    prix_unitaire: Decimal
    taux_tva: Decimal

    @property
    def ht(self) -> Decimal:
        return (self.quantite * self.prix_unitaire).quantize(Decimal("0.01"))

    @property
    def tva(self) -> Decimal:
        return (self.ht * self.taux_tva / 100).quantize(Decimal("0.01"))

    @property
    def ttc(self) -> Decimal:
        return self.ht + self.tva


@dataclass
class FacturePDFData:
    type: str           # "facture" | "devis"
    numero: str
    date_emission: date
    date_echeance: date | None
    emetteur_nom: str
    emetteur_adresse: str
    emetteur_siret: str
    emetteur_tva: str
    client_nom: str
    client_adresse: str
    client_email: str
    lignes: list[LignePDF]
    notes: str


_ACCENT = colors.HexColor("#7c3aed")
_LIGHT = colors.HexColor("#f5f3ff")
_GREY = colors.HexColor("#6b7280")
_DARK = colors.HexColor("#111827")
_BORDER = colors.HexColor("#e5e7eb")


def generate_pdf(data: FacturePDFData) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    W = A4[0] - 40 * mm

    st_title = ParagraphStyle("title", fontSize=22, textColor=_ACCENT,
                               fontName="Helvetica-Bold", spaceAfter=2)
    st_sub = ParagraphStyle("sub", fontSize=9, textColor=_GREY, fontName="Helvetica")
    st_label = ParagraphStyle("label", fontSize=8, textColor=_GREY,
                               fontName="Helvetica", spaceBefore=4)
    st_val = ParagraphStyle("val", fontSize=10, textColor=_DARK,
                             fontName="Helvetica-Bold")
    st_small = ParagraphStyle("small", fontSize=8, textColor=_GREY, fontName="Helvetica")
    st_right = ParagraphStyle("right", fontSize=10, textColor=_DARK,
                               fontName="Helvetica", alignment=TA_RIGHT)
    st_notes = ParagraphStyle("notes", fontSize=9, textColor=_GREY,
                               fontName="Helvetica", spaceBefore=6)

    label = "DEVIS" if data.type == "devis" else "FACTURE"
    story = []

    # ── Header row ─────────────────────────────────────────────────────────────
    emetteur_lines = f"{data.emetteur_nom}\n{data.emetteur_adresse}"
    if data.emetteur_siret:
        emetteur_lines += f"\nSIRET : {data.emetteur_siret}"
    if data.emetteur_tva:
        emetteur_lines += f"\nTVA : {data.emetteur_tva}"

    header_data = [[
        Paragraph(label, st_title),
        Paragraph(emetteur_lines.replace("\n", "<br/>"), st_sub),
    ]]
    header = Table(header_data, colWidths=[W * 0.4, W * 0.6])
    header.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(header)
    story.append(Spacer(1, 6 * mm))

    # ── Meta + Client ──────────────────────────────────────────────────────────
    echeance_txt = data.date_echeance.strftime("%d/%m/%Y") if data.date_echeance else "—"
    client_lines = data.client_nom
    if data.client_adresse:
        client_lines += "\n" + data.client_adresse
    if data.client_email:
        client_lines += "\n" + data.client_email

    meta_data = [
        [
            Paragraph(f"N° {data.numero}", st_val),
            Paragraph("FACTURÉ À", st_label),
        ],
        [
            Paragraph(f"Date : {data.date_emission.strftime('%d/%m/%Y')}", st_small),
            Paragraph(client_lines.replace("\n", "<br/>"), st_val),
        ],
        [
            Paragraph(f"Échéance : {echeance_txt}", st_small),
            Paragraph("", st_small),
        ],
    ]
    meta = Table(meta_data, colWidths=[W * 0.4, W * 0.6])
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (1, 0), (1, -1), _LIGHT),
        ("ROUNDEDCORNERS", [4]),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
        ("TOPPADDING", (1, 0), (1, 0), 8),
        ("BOTTOMPADDING", (1, -1), (1, -1), 8),
    ]))
    story.append(meta)
    story.append(Spacer(1, 8 * mm))

    # ── Lines table ────────────────────────────────────────────────────────────
    col_desc = W * 0.42
    col_qty = W * 0.1
    col_pu = W * 0.16
    col_tva = W * 0.1
    col_ht = W * 0.12
    col_ttc = W * 0.1

    headers = ["Description", "Qté", "P.U. HT", "TVA", "HT", "TTC"]
    rows = [headers]
    for l in data.lignes:
        rows.append([
            l.description,
            str(l.quantite.normalize()),
            f"{l.prix_unitaire:,.2f} €",
            f"{l.taux_tva}%",
            f"{l.ht:,.2f} €",
            f"{l.ttc:,.2f} €",
        ])

    total_ht = sum(l.ht for l in data.lignes)
    total_tva = sum(l.tva for l in data.lignes)
    total_ttc = total_ht + total_tva

    rows.append(["", "", "", "Sous-total HT", "", f"{total_ht:,.2f} €"])
    rows.append(["", "", "", "TVA", "", f"{total_tva:,.2f} €"])
    rows.append(["", "", "", "TOTAL TTC", "", f"{total_ttc:,.2f} €"])

    lines_table = Table(rows, colWidths=[col_desc, col_qty, col_pu, col_tva, col_ht, col_ttc])
    n = len(data.lignes)
    lines_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        # Data rows
        ("FONTSIZE", (0, 1), (-1, n), 9),
        ("TOPPADDING", (0, 1), (-1, n), 5),
        ("BOTTOMPADDING", (0, 1), (-1, n), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, n), [colors.white, _LIGHT]),
        ("GRID", (0, 0), (-1, n), 0.3, _BORDER),
        # Totals
        ("FONTNAME", (0, n + 1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, n + 1), (-1, -1), 9),
        ("TOPPADDING", (0, n + 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, n + 1), (-1, -1), 4),
        ("BACKGROUND", (0, -1), (-1, -1), _LIGHT),
        ("TEXTCOLOR", (-2, -1), (-1, -1), _ACCENT),
        ("FONTSIZE", (-2, -1), (-1, -1), 11),
        # Alignment
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("SPAN", (0, n + 1), (2, n + 1)),
        ("SPAN", (0, n + 2), (2, n + 2)),
        ("SPAN", (0, n + 3), (2, n + 3)),
        ("SPAN", (3, n + 1), (4, n + 1)),
        ("SPAN", (3, n + 2), (4, n + 2)),
        ("SPAN", (3, n + 3), (4, n + 3)),
        ("ALIGN", (3, n + 1), (4, -1), "RIGHT"),
    ]))
    story.append(lines_table)

    if data.notes:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(f"Notes : {data.notes}", st_notes))

    doc.build(story)
    return buf.getvalue()
