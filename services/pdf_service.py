from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import io

def generate_project_pdf(project, estimation):
    """
    Generate professional PDF report for construction project
    Returns: BytesIO buffer containing the PDF
    """
    
    # Create PDF buffer
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=1*inch,
        bottomMargin=0.75*inch
    )
    
    # Container for PDF elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#333333'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        textColor=colors.HexColor('#666666'),
        spaceAfter=10,
        spaceBefore=15,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    
    # ========== HEADER ==========
    elements.append(Paragraph("🏗️ HOUSE-FORGE", title_style))
    elements.append(Paragraph("Construction Estimation Report", styles['Heading2']))
    elements.append(Spacer(1, 0.3*inch))
    
    # ========== PROJECT INFORMATION ==========
    elements.append(Paragraph("PROJECT DETAILS", heading_style))
    
    project_info = [
        ['Project Name:', project.get('title', 'N/A')],
        ['Location:', project.get('location', 'N/A')],
        ['Total Area:', f"{project.get('square_feet', 0)} sq ft"],
        ['Rooms:', str(project.get('rooms', 0))],
        ['Floors:', str(project.get('floors', 0))],
        ['Bathrooms:', str(project.get('bathrooms', 0))],
        ['Property Type:', project.get('property_type', 'N/A').title()],
        ['Budget Range:', project.get('budget_range', 'medium').title()],
        ['Date:', datetime.now().strftime('%B %d, %Y')]
    ]
    
    project_table = Table(project_info, colWidths=[2*inch, 4*inch])
    project_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    elements.append(project_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # ========== COST SUMMARY ==========
    elements.append(Paragraph("COST SUMMARY", heading_style))
    
    budget = project.get('budget_range', 'medium')
    costs = estimation['costs'][budget]
    
    cost_summary = [
        ['Description', 'Amount (₹)'],
        ['Material Cost', f"₹{costs['material_cost']:,.0f}"],
        ['Labor Cost', f"₹{costs['labor_cost']:,.0f}"],
        ['Other Costs', f"₹{costs['other_costs']:,.0f}"],
        ['', ''],
        ['TOTAL ESTIMATED COST', f"₹{costs['total_cost']:,.0f}"]
    ]
    
    cost_table = Table(cost_summary, colWidths=[4*inch, 2*inch])
    cost_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -2), 'Helvetica'),
        ('FONTNAME', (1, 1), (1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTSIZE', (0, 1), (-1, -2), 10),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#667eea')),
    ]))
    
    elements.append(cost_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # ========== BUDGET COMPARISON ==========
    elements.append(Paragraph("BUDGET COMPARISON", heading_style))
    
    budget_comparison = [
        ['Budget Type', 'Material', 'Labor', 'Total'],
        ['Budget', 
         f"₹{estimation['costs']['low']['material_cost']:,.0f}",
         f"₹{estimation['costs']['low']['labor_cost']:,.0f}",
         f"₹{estimation['costs']['low']['total_cost']:,.0f}"],
        ['Standard', 
         f"₹{estimation['costs']['medium']['material_cost']:,.0f}",
         f"₹{estimation['costs']['medium']['labor_cost']:,.0f}",
         f"₹{estimation['costs']['medium']['total_cost']:,.0f}"],
        ['Premium', 
         f"₹{estimation['costs']['high']['material_cost']:,.0f}",
         f"₹{estimation['costs']['high']['labor_cost']:,.0f}",
         f"₹{estimation['costs']['high']['total_cost']:,.0f}"]
    ]
    
    budget_table = Table(budget_comparison, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    budget_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    elements.append(budget_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # ========== TIMELINE ==========
    elements.append(Paragraph("PROJECT TIMELINE", heading_style))
    
    timeline_text = f"Estimated Duration: <b>{estimation['timeline']['total_days']} days</b> (approximately {estimation['timeline']['total_days'] / 30:.1f} months)"
    elements.append(Paragraph(timeline_text, normal_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # ========== PAGE BREAK ==========
    elements.append(PageBreak())
    
    # ========== STAGE-WISE BREAKDOWN ==========
    elements.append(Paragraph("CONSTRUCTION STAGES BREAKDOWN", heading_style))
    elements.append(Spacer(1, 0.2*inch))
    
    stages = [
        ('foundation', 'Foundation'),
        ('walls', 'Walls'),
        ('flooring', 'Flooring & Slab'),
        ('roofing', 'Roofing'),
        ('plumbing', 'Plumbing'),
        ('electrical', 'Electrical'),
        ('finishing', 'Finishing'),
        ('carpentry', 'Carpentry & Interior'),
        ('exterior', 'Exterior & Landscaping'),
        ('miscellaneous', 'Miscellaneous')
    ]
    
    for stage_key, stage_name in stages:
        stage_cost = costs['stage_breakdown'][stage_key]
        
        elements.append(Paragraph(f"{stage_name.upper()}", subheading_style))
        elements.append(Paragraph(f"Stage Cost: <b>₹{stage_cost:,.0f}</b>", normal_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # Materials for this stage
        materials_data = [['Material', 'Quantity', 'Unit']]
        
        for material, quantity in estimation['materials'][stage_key].items():
            if quantity > 0:
                # Determine unit
                if 'bags' in material:
                    unit = 'bags'
                elif 'kg' in material:
                    unit = 'kg'
                elif 'cuft' in material:
                    unit = 'cu ft'
                elif 'sqft' in material:
                    unit = 'sq ft'
                elif 'meters' in material:
                    unit = 'meters'
                elif 'liters' in material:
                    unit = 'liters'
                elif 'sheets' in material:
                    unit = 'sheets'
                else:
                    unit = 'units'
                
                materials_data.append([
                    material.replace('_', ' ').title(),
                    f"{quantity:,.0f}",
                    unit
                ])
        
        if len(materials_data) > 1:
            materials_table = Table(materials_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
            materials_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')])
            ]))
            
            elements.append(materials_table)
        
        elements.append(Spacer(1, 0.2*inch))
    
    # ========== FOOTER ==========
    elements.append(Spacer(1, 0.4*inch))
    footer_text = f"""
    <para align=center>
    <b>This is a system-generated estimate from House-Forge</b><br/>
    Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br/>
    For support: support@house-forge.com
    </para>
    """
    elements.append(Paragraph(footer_text, normal_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF data
    buffer.seek(0)
    return buffer