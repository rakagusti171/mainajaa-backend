# backend/api/invoice.py
"""
Module untuk generate invoice PDF menggunakan ReportLab
"""
from io import BytesIO
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from decimal import Decimal

def generate_invoice_pdf(pembelian_data):
    """
    Generate PDF invoice untuk pembelian menggunakan ReportLab.
    
    Args:
        pembelian_data: Dictionary berisi data pembelian
        
    Returns:
        BytesIO object berisi PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#6B46C1'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#6B46C1'),
        spaceAfter=10
    )
    
    # Header
    story.append(Paragraph("MAINAJAA", title_style))
    story.append(Paragraph("Marketplace Akun Gaming", styles['Normal']))
    story.append(Paragraph("Invoice", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Invoice Info
    info_data = [
        ['Informasi Pembeli', 'Informasi Invoice'],
        [f"Nama: {pembelian_data.get('pembeli', {}).get('username', 'N/A')}", f"Kode: {pembelian_data.get('kode_transaksi', 'N/A')}"],
        [f"Email: {pembelian_data.get('pembeli', {}).get('email', 'N/A')}", f"Tanggal: {pembelian_data.get('tanggal', 'N/A')}"],
        ['', f"Status: {pembelian_data.get('status', 'PENDING')}"]
    ]
    
    info_table = Table(info_data, colWidths=[90*mm, 90*mm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6B46C1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Items Table
    story.append(Paragraph("Detail Pesanan", heading_style))
    
    items = pembelian_data.get('items', [])
    table_data = [['No', 'Item', 'Game', 'Harga', 'Qty', 'Subtotal']]
    
    for idx, item in enumerate(items, 1):
        table_data.append([
            str(idx),
            item.get('nama', 'N/A'),
            item.get('game', 'N/A'),
            f"Rp {item.get('harga', 0):,.0f}",
            str(item.get('quantity', 1)),
            f"Rp {item.get('subtotal', 0):,.0f}"
        ])
    
    items_table = Table(table_data, colWidths=[10*mm, 50*mm, 40*mm, 30*mm, 15*mm, 35*mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6B46C1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 20))
    
    # Total Section
    subtotal = pembelian_data.get('subtotal', 0)
    diskon = pembelian_data.get('diskon', 0)
    total = pembelian_data.get('total', 0)
    
    total_data = [
        ['Subtotal:', f"Rp {subtotal:,.0f}"]
    ]
    
    if diskon > 0:
        total_data.append(['Diskon:', f"- Rp {diskon:,.0f}"])
    
    total_data.append(['TOTAL:', f"Rp {total:,.0f}"])
    
    total_table = Table(total_data, colWidths=[120*mm, 60*mm])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 14),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#6B46C1')),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor('#6B46C1')),
        ('TOPPADDING', (0, -1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 30))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    story.append(Paragraph("Terima kasih telah berbelanja di MainAjaa!", footer_style))
    story.append(Paragraph("Invoice ini adalah bukti transaksi yang sah.", footer_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def create_invoice_response(pembelian_data, filename=None):
    """
    Create HTTP response dengan PDF invoice.
    
    Args:
        pembelian_data: Dictionary berisi data pembelian
        filename: Nama file untuk download (optional)
        
    Returns:
        HttpResponse dengan PDF
    """
    pdf_buffer = generate_invoice_pdf(pembelian_data)
    
    if not filename:
        filename = f"invoice_{pembelian_data.get('kode_transaksi', 'unknown')}.pdf"
    
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response
