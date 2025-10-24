# utils/pdf_generator.py
"""
Utility to generate PDF reports, starting with the CoC Report.
ADDED: UoM, Shelf Life, Batch Number, PO Number to Header Info Table.
ADDED: UoM to Component Detail Table.
Adjusted layouts and column widths.
REVISED: Header table layout for better readability and alignment.
FIXED: Handle potential NoneType error during PDF generation for display strings and other header values.
"""
import io
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

def generate_coc_pdf(job_details, app_root_path):
    """
    Generates a Certificate of Compliance PDF from the job_details dictionary.

    :param job_details: Dictionary containing CoC data
    :param app_root_path: The root path of the Flask application (from current_app.root_path)
    """

    def _header_footer_layout(canvas, doc):
        """
        Draws the custom header (logo, address) and footer (static text)
        on each page. Footer is back at the original bottom position.
        """
        canvas.saveState()

        page_width = doc.width + doc.leftMargin + doc.rightMargin
        page_height = doc.height + doc.topMargin + doc.bottomMargin

        # === HEADER === (Unchanged logo/address part)
        # --- Address lines ---
        address_top_y = page_height - 0.5*inch
        canvas.setFont('Helvetica', 9)
        canvas.drawRightString(page_width - doc.rightMargin, address_top_y, "2745 HUNTINGTON DRIVE")
        address_next_y = address_top_y - 0.16*inch
        canvas.drawRightString(page_width - doc.rightMargin, address_next_y, "DUARTE, CALIFORNIA 91010")

        # --- Logo ---
        logo_filename = 'WPIA_Main_Light.png'
        logo_path = os.path.join(app_root_path, 'static', 'img', logo_filename)
        try:
            img = ImageReader(logo_path)
            img_width, img_height = img.getSize()
            logo_draw_width = 3.0 * inch
            aspect_ratio = img_height / img_width if img_width > 0 else 1
            logo_draw_height = logo_draw_width * aspect_ratio
            logo_left_x = doc.leftMargin - 0.3 * inch
            top_gap = 0.1 * inch
            logo_top_y = page_height - top_gap
            logo_bottom_y = logo_top_y - logo_draw_height
            canvas.drawImage(img, logo_left_x, logo_bottom_y,
                             width=logo_draw_width,
                             height=logo_draw_height,
                             preserveAspectRatio=True,
                             mask='auto')
        except Exception as e:
            print(f"--- PDF DEBUG: ERROR drawing logo: {e}")

        # === FOOTER === (Back to original Y positions)
        # --- Page Number ---
        canvas.setFont('Helvetica', 8)
        canvas.drawCentredString(page_width / 2.0, 0.5 * inch, f"Page {canvas.getPageNumber()}") # Original Y

        # --- Signature Block ---
        y_sig_block = 0.8 * inch # Original Y
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawString(doc.leftMargin, y_sig_block + 5, "Authorized Signature:")
        canvas.line(doc.leftMargin + 1.4*inch, y_sig_block, doc.leftMargin + 3.5*inch, y_sig_block) # Line
        canvas.drawString(doc.leftMargin + 3.75*inch, y_sig_block + 5, "Date:")
        canvas.line(doc.leftMargin + 4.1*inch, y_sig_block, doc.leftMargin + 5.5*inch, y_sig_block) # Line
        canvas.drawString(doc.leftMargin + 5.75*inch, y_sig_block + 5, "Title:")
        canvas.line(doc.leftMargin + 6.1*inch, y_sig_block, doc.leftMargin + 8.0*inch, y_sig_block) # Line

        # --- Statement of Compliance ---
        styles = getSampleStyleSheet()
        statement_title_style = ParagraphStyle( name='FooterTitle', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', alignment=TA_CENTER)
        statement_body_style = ParagraphStyle( name='FooterBody', parent=styles['Normal'], fontSize=8, fontName='Helvetica', alignment=TA_LEFT, leading=10)
        title_text = "Statement of Compliance:"
        body_text = (
            "This certifies that the subject material has been manufactured according to the relevant material Specifications and Standard Operating Procedures. "
            "That any deviations from standard specifications and procedures have been properly approved, documented, and reported above. "
            "That the material has been inspected and tested according to the specified quality requirements, and that it meets the specified requirements. "
            "That the manufacturing and quality assurance processes have been properly documented, and that the documents are available for review. "
            "That this product has not been altered, and no biological contamination has been introduced during the packaging process."
        )
        title_p = Paragraph(title_text, statement_title_style)
        body_p = Paragraph(body_text, statement_body_style)
        available_width = doc.width
        title_w, title_h = title_p.wrapOn(canvas, available_width, 0)
        body_w, body_h = body_p.wrapOn(canvas, available_width, 0)

        # Original Y positions
        y_pos_body = y_sig_block + 0.3 * inch
        body_p.drawOn(canvas, doc.leftMargin, y_pos_body)
        y_pos_title = y_pos_body + body_h + 4
        title_p.drawOn(canvas, doc.leftMargin, y_pos_title)

        canvas.restoreState()

    # --- Document Setup ---
    buffer = io.BytesIO()
    adjusted_top_margin = (1.8*inch) - 0.5*inch
    original_bottom_margin = 2.0*inch
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=0.5*inch, leftMargin=0.5*inch,
                            topMargin=adjusted_top_margin,
                            bottomMargin=original_bottom_margin)

    # --- Story Building ---
    story = []
    styles = getSampleStyleSheet()
    # Style for potentially multi-line content in the header table
    multiline_style = ParagraphStyle(name='MultiLine', parent=styles['Normal'], leading=12)
    # Style for right-aligned numeric values in header
    numeric_style_right = ParagraphStyle(name='NumericRight', parent=styles['Normal'], alignment=TA_RIGHT)
    # Style for left-aligned numeric values in header
    numeric_style_left = ParagraphStyle(name='NumericLeft', parent=styles['Normal'], alignment=TA_LEFT)


    # --- Title ---
    title_style = ParagraphStyle(name='TitleStyle', fontSize=16, alignment=TA_CENTER, fontName='Helvetica-Bold')
    story.append(Paragraph("SALEABLE PRODUCT CERTIFICATE OF COMPLIANCE", title_style))
    story.append(Spacer(1, 0.25*inch))

    # --- REVISED Header Info Table --- (2-Column Layout, better alignment)
    # Prepare potentially multi-line values, ensuring they are strings
    # <<< MODIFIED: Ensure ALL .get() results used as text are cast to str >>>
    batch_number_display = job_details.get('batch_number_display', 'N/A')
    batch_number_text = str(batch_number_display).replace('<br>', '\n') if batch_number_display else 'N/A'

    shelf_life_display = job_details.get('shelf_life_display', 'N/A')
    shelf_life_text = str(shelf_life_display).replace(', ', '\n') if shelf_life_display else 'N/A'

    job_number_val = str(job_details.get('job_number', 'N/A'))
    customer_val = str(job_details.get('customer_name', 'N/A'))
    part_number_val = str(job_details.get('part_number', 'N/A'))
    sales_order_val = str(job_details.get('sales_order', 'N/A'))
    uom_val = str(job_details.get('unit_of_measure', 'N/A'))
    po_number_val = str(job_details.get('customer_po', 'N/A'))
    part_desc_val = str(job_details.get('part_description', 'N/A'))
    req_qty_val = f"{job_details.get('required_qty', 0.0):,.2f}"
    comp_qty_val = f"{job_details.get('completed_qty', 0.0):,.2f}"
    # <<< END MODIFIED >>>

    header_data_revised = [
        # Row 1
        [Paragraph("<b>Job Number:</b>", styles['Normal']),
         Paragraph(job_number_val, styles['Normal']), # Use prepared string var
         Paragraph("<b>Customer:</b>", styles['Normal']),
         Paragraph(customer_val, multiline_style)], # Use prepared string var
        # Row 2
        [Paragraph("<b>Part Number:</b>", styles['Normal']),
         Paragraph(part_number_val, styles['Normal']), # Use prepared string var
         Paragraph("<b>Sales Order:</b>", styles['Normal']),
         Paragraph(sales_order_val, styles['Normal'])], # Use prepared string var
        # Row 3
        [Paragraph("<b>UoM:</b>", styles['Normal']),
         Paragraph(uom_val, styles['Normal']), # Use prepared string var
         Paragraph("<b>PO Number:</b>", styles['Normal']),
         Paragraph(po_number_val, styles['Normal'])], # Use prepared string var
        # Row 4 (Part Description spans all 4 cols)
        [Paragraph("<b>Part Description:</b>", styles['Normal']),
         Paragraph(part_desc_val, multiline_style), # Use prepared string var
         "", ""],
        # Row 5 - Quantities aligned left, Labels aligned left
        [Paragraph("<b>Required Qty:</b>", styles['Normal']),
         Paragraph(req_qty_val, numeric_style_left), # Use prepared string var
         Paragraph("<b>Shelf Life:</b>", styles['Normal']),
         Paragraph(shelf_life_text, multiline_style)], # Use prepared string var
        # Row 6 - Quantities aligned left, Labels aligned left
        [Paragraph("<b>Completed Qty:</b>", styles['Normal']),
         Paragraph(comp_qty_val, numeric_style_left), # Use prepared string var
         Paragraph("<b>Batch Number:</b>", styles['Normal']),
         Paragraph(batch_number_text, multiline_style)], # Use prepared string var
    ]

    # Column widths for revised 4-column layout (Label, Value, Label, Value) - Total 10 inches
    header_col_widths_revised = [1.3*inch, 3.7*inch, 1.3*inch, 3.7*inch]

    header_table_revised = Table(header_data_revised, colWidths=header_col_widths_revised)
    header_table_revised.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        # Span Part Description across columns 1, 2, 3 in Row 4 (index 3)
        ('SPAN', (1, 3), (3, 3)),
        # Apply right padding to labels in columns 0 and 2 for spacing
        ('RIGHTPADDING', (0, 0), (0, -1), 10), # First column labels
        ('RIGHTPADDING', (2, 0), (2, -1), 10), # Third column labels
    ]))

    story.append(header_table_revised)
    story.append(Spacer(1, 0.25*inch))


    # --- Main Component Table --- (Unchanged from previous version with UoM)
    header_style_center = ParagraphStyle(name='HeaderCenter', fontSize=9, fontName='Helvetica-Bold', alignment=TA_CENTER)
    header_style_left = ParagraphStyle(name='HeaderLeft', fontSize=9, fontName='Helvetica-Bold', alignment=TA_LEFT)
    body_style_center = ParagraphStyle(name='BodyCenter', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)
    body_style_left = ParagraphStyle(name='BodyLeft', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT)

    table_headers = [
        Paragraph("Part", header_style_left),
        Paragraph("Part Description", header_style_left),
        Paragraph("UoM", header_style_center),
        Paragraph("Lot #", header_style_center),
        Paragraph("Exp Date", header_style_center),
        Paragraph("Starting Lot Qty", header_style_center),
        Paragraph("Ending Inventory", header_style_center),
        Paragraph("Packaged Qty", header_style_center),
        Paragraph("Yield Cost/Scrap", header_style_center),
        Paragraph("Yield Loss", header_style_center)
    ]
    col_widths = [ 0.9*inch, 2.0*inch, 0.5*inch, 1.1*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch, 0.5*inch ]
    table_data = [table_headers]
    table_styles = [
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,1), (-1,-1), 'CENTER'),
        ('ALIGN', (0,1), (1,-1), 'LEFT'),
        ('FONTSIZE', (0,1), (-1,-1), 9),
    ]

    current_row = 1
    if not job_details.get('grouped_list'):
        table_data.append([ Paragraph("No component transactions found for this job.", body_style_center), "", "", "", "", "", "", "", "", "" ])
        table_styles.append(('SPAN', (0, 1), (-1, 1)))
    else:
        for part_num, group in job_details.get('grouped_list', {}).items():
            num_lots = len(group['lots'])
            if num_lots == 0: continue
            start_row = current_row
            end_row = current_row + num_lots - 1
            if num_lots > 1:
                table_styles.append(('SPAN', (0, start_row), (0, end_row))) # Part
                table_styles.append(('SPAN', (1, start_row), (1, end_row))) # Desc
                table_styles.append(('SPAN', (2, start_row), (2, end_row))) # UoM
            table_styles.append(('VALIGN', (0, start_row), (2, end_row), 'MIDDLE'))
            for i, lot_summary in enumerate(group['lots']):
                part_cell_text = part_num if i == 0 else ""
                desc_cell_text = group.get('part_description', 'N/A') if i == 0 else ""
                uom_cell_text = group.get('unit_of_measure', 'N/A') if i == 0 else ""

                part_cell = Paragraph(part_cell_text, body_style_left)
                desc_cell = Paragraph(desc_cell_text, body_style_left)
                uom_cell = Paragraph(uom_cell_text, body_style_center)
                lot_cell = Paragraph(lot_summary.get('lot_number', 'N/A'), body_style_center)
                exp_cell = Paragraph(lot_summary.get('exp_date', 'N/A'), body_style_center)
                start_qty_str = f"{lot_summary.get('Starting Lot Qty', 0.0):,.2f}"
                end_inv_str = f"{lot_summary.get('Ending Inventory', 0.0):,.2f}"
                pkg_qty_str = f"{lot_summary.get('Packaged Qty', 0.0):,.2f}"
                yield_cost_str = f"{lot_summary.get('Yield Cost/Scrap', 0.0):,.2f}"
                yield_loss_str = f"{lot_summary.get('Yield Loss', 0.0):.2f}%"

                row_data = [ part_cell, desc_cell, uom_cell, lot_cell, exp_cell, start_qty_str, end_inv_str, pkg_qty_str, yield_cost_str, yield_loss_str ]
                table_data.append(row_data)
                current_row += 1

    component_table = Table(table_data, colWidths=col_widths)
    component_table.setStyle(TableStyle(table_styles))
    story.append(component_table)

    # Build the PDF
    doc.build(story, onFirstPage=_header_footer_layout, onLaterPages=_header_footer_layout)

    buffer.seek(0)
    filename = f"CoC_{job_details.get('job_number', '000000000')}.pdf"

    return buffer, filename