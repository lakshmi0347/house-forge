from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
import io

BRAND       = colors.HexColor('#B5804F')
BRAND_DARK  = colors.HexColor('#8C5E35')
BRAND_LIGHT = colors.HexColor('#F7EDE2')
GREY_LIGHT  = colors.HexColor('#F0EBE3')
GREY_MID    = colors.HexColor('#E2D9CE')
DARK        = colors.HexColor('#1C1917')
MUTED       = colors.HexColor('#9C8E84')


def _fmt(value, prefix=""):
    try:
        return f"{prefix}₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


def generate_project_pdf(project, estimation):
    """
    Generate professional PDF report.
    - Labour row hidden when estimate_scope = material_only (labor_cost = 0)
    - All dict access uses .get() — no KeyError crashes
    - AI rationale shown when present
    - Brand colours matching the House-Forge UI
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=0.75*inch, leftMargin=0.75*inch,
        topMargin=1.0*inch,    bottomMargin=0.75*inch,
    )
    elements = []
    styles   = getSampleStyleSheet()

    title_s = ParagraphStyle('HFT', parent=styles['Heading1'],
        fontSize=26, textColor=BRAND, spaceAfter=4,
        alignment=TA_CENTER, fontName='Helvetica-Bold')
    sub_s   = ParagraphStyle('HFS', parent=styles['Normal'],
        fontSize=12, textColor=MUTED, spaceAfter=18,
        alignment=TA_CENTER, fontName='Helvetica')
    h2_s    = ParagraphStyle('HFH2', parent=styles['Heading2'],
        fontSize=14, textColor=DARK, spaceAfter=8, spaceBefore=16,
        fontName='Helvetica-Bold')
    h3_s    = ParagraphStyle('HFH3', parent=styles['Heading3'],
        fontSize=12, textColor=BRAND_DARK, spaceAfter=6, spaceBefore=10,
        fontName='Helvetica-Bold')
    norm    = styles['Normal']
    note_s  = ParagraphStyle('HFN', parent=styles['Normal'],
        fontSize=9, textColor=MUTED, fontName='Helvetica-Oblique')
    ctr_s   = ParagraphStyle('HFC', parent=styles['Normal'],
        fontSize=9, alignment=TA_CENTER, fontName='Helvetica')

    # ── HEADER ──────────────────────────────────────────────────
    elements += [
        Paragraph("HOUSE-FORGE", title_s),
        Paragraph("Construction Estimation Report", sub_s),
        Spacer(1, 0.1*inch),
    ]

    # ── PROJECT DETAILS ──────────────────────────────────────────
    elements.append(Paragraph("PROJECT DETAILS", h2_s))

    scope_raw   = str(project.get('estimate_scope', 'material_only'))
    scope_label = 'Material + Labour' if scope_raw == 'material_and_labour' else 'Material Only'
    budget_raw  = str(project.get('budget_range', 'medium')).lower()
    budget_label= {'low':'Budget','medium':'Standard','high':'Premium'}.get(budget_raw, budget_raw.title())

    proj_rows = [
        ['Project Name',   str(project.get('title',       'N/A'))],
        ['Location',       str(project.get('location',    'N/A'))],
        ['Total BUA',      f"{project.get('square_feet',0)} sq ft"],
        ['Plot Area',      f"{project.get('plot_area','N/A')} sq ft"],
        ['Rooms',          str(project.get('rooms',       'N/A'))],
        ['Floors',         str(project.get('floors',      'N/A'))],
        ['Bathrooms',      str(project.get('bathrooms',   'N/A'))],
        ['Property Type',  str(project.get('property_type','N/A')).title()],
        ['Estimate Scope', scope_label],
        ['Budget Range',   budget_label],
        ['Report Date',    datetime.now().strftime('%B %d, %Y')],
    ]
    pt = Table(proj_rows, colWidths=[2.0*inch, 4.5*inch])
    pt.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(0,-1), GREY_LIGHT),
        ('FONTNAME',     (0,0),(0,-1), 'Helvetica-Bold'),
        ('FONTNAME',     (1,0),(1,-1), 'Helvetica'),
        ('FONTSIZE',     (0,0),(-1,-1), 10),
        ('ALIGN',        (0,0),(0,-1), 'RIGHT'),
        ('TOPPADDING',   (0,0),(-1,-1), 7),
        ('BOTTOMPADDING',(0,0),(-1,-1), 7),
        ('LEFTPADDING',  (0,0),(-1,-1), 10),
        ('GRID',         (0,0),(-1,-1), 0.5, GREY_MID),
    ]))
    elements += [pt, Spacer(1, 0.3*inch)]

    # ── COST SUMMARY ─────────────────────────────────────────────
    elements.append(Paragraph("COST SUMMARY", h2_s))

    costs     = estimation.get('costs', {})
    tc        = costs.get(budget_raw, costs.get('medium', {}))
    mat_cost  = tc.get('material_cost', 0)
    lab_cost  = tc.get('labor_cost',    0)
    oth_cost  = tc.get('other_costs',   0)
    total     = tc.get('total_cost',    0)

    cost_rows = [['Description', 'Amount']]
    cost_rows.append(['Material Cost', _fmt(mat_cost)])
    if float(lab_cost or 0) > 0:
        cost_rows.append(['Labour Cost', _fmt(lab_cost)])
    cost_rows.append(['Other / Contingency', _fmt(oth_cost)])
    cost_rows.append(['', ''])
    cost_rows.append(['TOTAL ESTIMATED COST', _fmt(total)])

    ct = Table(cost_rows, colWidths=[4.0*inch, 2.5*inch])
    ct.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,0), BRAND),
        ('TEXTCOLOR',    (0,0),(-1,0), colors.white),
        ('FONTNAME',     (0,0),(-1,0), 'Helvetica-Bold'),
        ('FONTNAME',     (0,1),(-1,-2),'Helvetica'),
        ('FONTNAME',     (0,-1),(-1,-1),'Helvetica-Bold'),
        ('FONTSIZE',     (0,0),(-1,0), 11),
        ('FONTSIZE',     (0,1),(-1,-2),10),
        ('FONTSIZE',     (0,-1),(-1,-1),12),
        ('ALIGN',        (1,0),(1,-1), 'RIGHT'),
        ('TOPPADDING',   (0,0),(-1,-1),9),
        ('BOTTOMPADDING',(0,0),(-1,-1),9),
        ('LEFTPADDING',  (0,0),(-1,-1),10),
        ('BACKGROUND',   (0,-1),(-1,-1), GREY_LIGHT),
        ('LINEABOVE',    (0,-1),(-1,-1), 1.5, BRAND),
        ('GRID',         (0,0),(-1,-2), 0.5, GREY_MID),
    ]))
    elements += [ct, Spacer(1, 0.3*inch)]

    # ── BUDGET COMPARISON ────────────────────────────────────────
    elements.append(Paragraph("BUDGET COMPARISON", h2_s))

    lc = costs.get('low',    {})
    mc = costs.get('medium', {})
    hc = costs.get('high',   {})
    show_lab = float(mc.get('labor_cost', 0)) > 0

    if show_lab:
        hdr = ['Tier', 'Material', 'Labour', 'Other', 'Total']
        cmp = [hdr,
               ['Budget',   _fmt(lc.get('material_cost',0)), _fmt(lc.get('labor_cost',0)),
                _fmt(lc.get('other_costs',0)), _fmt(lc.get('total_cost',0))],
               ['Standard', _fmt(mc.get('material_cost',0)), _fmt(mc.get('labor_cost',0)),
                _fmt(mc.get('other_costs',0)), _fmt(mc.get('total_cost',0))],
               ['Premium',  _fmt(hc.get('material_cost',0)), _fmt(hc.get('labor_cost',0)),
                _fmt(hc.get('other_costs',0)), _fmt(hc.get('total_cost',0))],
        ]
        cw = [1.2*inch, 1.4*inch, 1.2*inch, 1.2*inch, 1.5*inch]
    else:
        hdr = ['Tier', 'Material Cost', 'Other', 'Total Cost']
        cmp = [hdr,
               ['Budget',   _fmt(lc.get('material_cost',0)), _fmt(lc.get('other_costs',0)), _fmt(lc.get('total_cost',0))],
               ['Standard', _fmt(mc.get('material_cost',0)), _fmt(mc.get('other_costs',0)), _fmt(mc.get('total_cost',0))],
               ['Premium',  _fmt(hc.get('material_cost',0)), _fmt(hc.get('other_costs',0)), _fmt(hc.get('total_cost',0))],
        ]
        cw = [1.4*inch, 2.0*inch, 1.4*inch, 1.7*inch]

    tier_row = {'low': 1, 'medium': 2, 'high': 3}.get(budget_raw, 2)
    cmt = Table(cmp, colWidths=cw)
    cmt.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,0), BRAND),
        ('TEXTCOLOR',    (0,0),(-1,0), colors.white),
        ('FONTNAME',     (0,0),(-1,0), 'Helvetica-Bold'),
        ('FONTNAME',     (0,1),(-1,-1),'Helvetica'),
        ('FONTSIZE',     (0,0),(-1,-1), 10),
        ('ALIGN',        (0,0),(-1,-1),'CENTER'),
        ('TOPPADDING',   (0,0),(-1,-1), 8),
        ('BOTTOMPADDING',(0,0),(-1,-1), 8),
        ('GRID',         (0,0),(-1,-1), 0.5, GREY_MID),
        ('BACKGROUND',   (0,tier_row),(-1,tier_row), BRAND_LIGHT),
        ('FONTNAME',     (0,tier_row),(-1,tier_row), 'Helvetica-Bold'),
    ]))
    elements += [cmt, Spacer(1, 0.3*inch)]

    # ── TIMELINE ─────────────────────────────────────────────────
    elements.append(Paragraph("PROJECT TIMELINE", h2_s))
    tl         = estimation.get('timeline', {})
    total_days = tl.get('total_days', 0)
    months     = round(float(total_days or 0) / 30, 1)
    elements.append(Paragraph(
        f"Estimated Duration: <b>{total_days} days</b> (~<b>{months} months</b>)", norm))

    tl_rows = [['Stage', 'Days']] + [
        [s.title(), str(int(tl.get(k, 0)))]
        for k, s in [('foundation','Foundation'),('walls','Walls'),('flooring','Flooring'),
                     ('roofing','Roofing'),('plumbing','Plumbing'),('electrical','Electrical'),
                     ('finishing','Finishing'),('carpentry','Carpentry'),('exterior','Exterior')]
    ]
    tlt = Table(tl_rows, colWidths=[3.5*inch, 1.5*inch])
    tlt.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,0), BRAND),
        ('TEXTCOLOR',    (0,0),(-1,0), colors.white),
        ('FONTNAME',     (0,0),(-1,0), 'Helvetica-Bold'),
        ('FONTNAME',     (0,1),(-1,-1),'Helvetica'),
        ('FONTSIZE',     (0,0),(-1,-1), 10),
        ('ALIGN',        (1,0),(1,-1), 'CENTER'),
        ('TOPPADDING',   (0,0),(-1,-1), 6),
        ('BOTTOMPADDING',(0,0),(-1,-1), 6),
        ('LEFTPADDING',  (0,0),(-1,-1), 10),
        ('GRID',         (0,0),(-1,-1), 0.4, GREY_MID),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, GREY_LIGHT]),
    ]))
    elements += [Spacer(1, 0.1*inch), tlt, Spacer(1, 0.3*inch)]

    # ── AI RATIONALE (only when AI returned data) ────────────────
    ai_rat = estimation.get('ai_rationale',  '')
    ai_con = estimation.get('ai_confidence', '')
    if ai_rat:
        elements.append(Paragraph("AI ESTIMATE REVIEW", h2_s))
        conf = f" (Confidence: {ai_con}/10)" if ai_con else ""
        elements.append(Paragraph(f"<i>{ai_rat}</i>{conf}", note_s))
        elements.append(Spacer(1, 0.2*inch))

    # ── PAGE BREAK → STAGE BOQ ──────────────────────────────────
    elements.append(PageBreak())
    elements.append(Paragraph("CONSTRUCTION STAGES & BILL OF QUANTITIES", h2_s))
    elements.append(Spacer(1, 0.1*inch))

    stage_defs = [
        ('foundation',    'Foundation'),
        ('walls',         'Walls'),
        ('flooring',      'Flooring & Slab'),
        ('roofing',       'Roofing'),
        ('plumbing',      'Plumbing'),
        ('electrical',    'Electrical'),
        ('finishing',     'Finishing'),
        ('carpentry',     'Carpentry & Interior'),
        ('exterior',      'Exterior & Landscaping'),
        ('miscellaneous', 'Miscellaneous'),
    ]
    stage_bd  = tc.get('stage_breakdown', {})
    materials = estimation.get('materials', {})

    for sk, sl in stage_defs:
        sc = stage_bd.get(sk, 0)
        elements.append(Paragraph(sl, h3_s))
        elements.append(Paragraph(f"Stage Cost: <b>{_fmt(sc)}</b>", norm))
        elements.append(Spacer(1, 0.06*inch))

        mats = materials.get(sk, {})
        mrows = [['Material', 'Quantity', 'Unit']]
        for mat, qty in mats.items():
            try:
                q = float(qty)
            except (TypeError, ValueError):
                continue
            if q <= 0:
                continue
            kl = mat.lower()
            if 'bags' in kl:       unit = 'bags'
            elif '_kg' in kl or kl.endswith('kg'): unit = 'kg'
            elif 'cuft' in kl:     unit = 'cu ft'
            elif 'sqft' in kl:     unit = 'sq ft'
            elif 'meters' in kl:   unit = 'meters'
            elif 'liters' in kl:   unit = 'liters'
            elif 'sheets' in kl:   unit = 'sheets'
            else:                  unit = 'nos'
            mrows.append([mat.replace('_',' ').title(), f"{q:,.0f}", unit])

        if len(mrows) > 1:
            mt = Table(mrows, colWidths=[3.2*inch, 1.6*inch, 1.7*inch])
            mt.setStyle(TableStyle([
                ('BACKGROUND',   (0,0),(-1,0), GREY_LIGHT),
                ('FONTNAME',     (0,0),(-1,0), 'Helvetica-Bold'),
                ('FONTNAME',     (0,1),(-1,-1),'Helvetica'),
                ('FONTSIZE',     (0,0),(-1,-1), 9),
                ('ALIGN',        (1,0),(-1,-1),'RIGHT'),
                ('ALIGN',        (0,0),(0,-1), 'LEFT'),
                ('TOPPADDING',   (0,0),(-1,-1), 5),
                ('BOTTOMPADDING',(0,0),(-1,-1), 5),
                ('LEFTPADDING',  (0,0),(-1,-1), 8),
                ('GRID',         (0,0),(-1,-1), 0.4, GREY_MID),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, GREY_LIGHT]),
            ]))
            elements.append(mt)
        elements.append(Spacer(1, 0.18*inch))

    # ── FOOTER ──────────────────────────────────────────────────
    elements.append(Spacer(1, 0.3*inch))
    for line in [
        "<b>This is a system-generated estimate from House-Forge.</b>",
        f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        "Estimates are indicative. Actual costs may vary with site conditions and market rates.",
        "For support: support@house-forge.com",
    ]:
        elements.append(Paragraph(line, ctr_s))
        elements.append(Spacer(1, 0.03*inch))

    doc.build(elements)
    buffer.seek(0)
    return buffer