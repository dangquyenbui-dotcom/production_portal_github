# utils/pdf_generator.py
"""
Utility to generate PDF reports, starting with the CoC Report.
Adjusted logo size and Y-coordinate for better placement.
Using wpia_main_light.png.
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
        on each page.
        """
        canvas.saveState()

        page_width = doc.width + doc.leftMargin + doc.rightMargin
        page_height = doc.height + doc.topMargin + doc.bottomMargin

        # === HEADER ===

        # --- Address lines (Drawn First) ---
        text_y_address = page_height - 0.5*inch
        canvas.setFont('Helvetica', 9)
        canvas.drawRightString(page_width - doc.rightMargin, text_y_address, "2745 HUNTINGTON DRIVE")
        text_y_address -= 0.16*inch
        canvas.drawRightString(page_width - doc.rightMargin, text_y_address, "DUARTE, CALIFORNIA 91010")

        # --- Logo (Drawn Last in Header) ---
        print(f"--- PDF DEBUG: app_root_path = {app_root_path}")

        # Using WPIA_Main_Light.png
        logo_filename = 'WPIA_Main_Light.png'
        logo_path = os.path.join(app_root_path, 'static', 'img', logo_filename)

        print(f"--- PDF DEBUG: Calculated logo_path = {logo_path}")

        img = None
        try:
            print(f"--- PDF DEBUG: Attempting to load image with ImageReader: {logo_path}")
            try:
                img = ImageReader(logo_path)
                img_width, img_height = img.getSize()
                print(f"--- PDF DEBUG: ImageReader successfully loaded image. Size: {img_width}x{img_height}")
            except Exception as ir_e:
                print(f"--- PDF DEBUG: ERROR - ImageReader failed to load image: {ir_e}")
                raise ir_e

            # <<< MODIFICATION: Adjust size and Y position >>>
            logo_draw_width = 2.5 * inch # Increased size from 2.0
            aspect_ratio = img_height / img_width if img_width > 0 else 1
            logo_draw_height = logo_draw_width * aspect_ratio

            # Position the TOP of the logo closer to the top margin
            top_margin_pos = page_height - doc.topMargin
            top_gap = 0.05 * inch # Reduced gap from 0.1
            logo_top_y = top_margin_pos - top_gap
            logo_bottom_y = logo_top_y - logo_draw_height

            # Keep the slight right shift
            logo_left_x = doc.leftMargin + 0.2 * inch
            # <<< END MODIFICATION >>>

            print(f"--- PDF DEBUG: Calculated draw width={logo_draw_width}, height={logo_draw_height}, Top Y={logo_top_y}, Bottom Y={logo_bottom_y}, Left X={logo_left_x}")

            print(f"--- PDF DEBUG: Attempting drawImage using ImageReader object at x={logo_left_x}, y={logo_bottom_y}")
            canvas.drawImage(img, logo_left_x, logo_bottom_y,
                             width=logo_draw_width,
                             height=logo_draw_height,
                             preserveAspectRatio=True,
                             mask='auto')
            print(f"--- PDF DEBUG: Successfully called drawImage for logo using ImageReader object.")

        except Exception as e:
            print(f"--- PDF DEBUG: ERROR drawing logo: {e}")


        # === FOOTER (Restored) ===
        # ... (rest of the footer code remains the same) ...
        # --- Page Number ---
        canvas.setFont('Helvetica', 8)
        canvas.drawCentredString(page_width / 2.0, 0.5 * inch, f"Page {canvas.getPageNumber()}")

        # --- Signature Block ---
        y_sig_block = 0.8 * inch
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
        y_pos_body = y_sig_block + 0.3 * inch
        body_p.drawOn(canvas, doc.leftMargin, y_pos_body)
        y_pos_title = y_pos_body + body_h + 4
        title_p.drawOn(canvas, doc.leftMargin, y_pos_title)

        canvas.restoreState()

    # --- Rest of the function (SimpleDocTemplate, story, build) remains unchanged ---
    buffer = io.BytesIO()
    # <<< MODIFICATION: Adjust top margin back slightly, fine-tune later if needed >>>
    adjusted_top_margin = 1.5*inch # Reduced from 2.5, increased from original 1.2
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=0.5*inch, leftMargin=0.5*inch,
                            topMargin=adjusted_top_margin, bottomMargin=2.0*inch)

    story = []
    styles = getSampleStyleSheet()

    # --- Title ---
    title_style = ParagraphStyle(name='TitleStyle', fontSize=16, alignment=TA_CENTER, fontName='Helvetica-Bold')
    story.append(Paragraph("SALEABLE PRODUCT CERTIFICATE OF COMPLIANCE", title_style))
    story.append(Spacer(1, 0.25*inch))

    # --- Header Info Table ---
    header_data = [
        [Paragraph("<b>Job Number:</b>", styles['Normal']),
         Paragraph(job_details.get('job_number', 'N/A'), styles['Normal']),
         Paragraph("<b>Part Number:</b>", styles['Normal']),
         Paragraph(job_details.get('part_number', 'N/A'), styles['Normal'])],

        [Paragraph("<b>Sales Order:</b>", styles['Normal']),
         Paragraph(job_details.get('sales_order', 'N/A'), styles['Normal']),
         Paragraph("<b>Part Description:</b>", styles['Normal']),
         Paragraph(job_details.get('part_description', 'N/A'), styles['Normal'])],

        [Paragraph("<b>Customer:</b>", styles['Normal']),
         Paragraph(job_details.get('customer_name', 'N/A'), styles['Normal']),
         Paragraph("<b>Completed Qty:</b>", styles['Normal']),
         Paragraph(f"{job_details.get('completed_qty', 0.0):,.2f}", styles['Normal'])],

        [Paragraph("<b>Required Qty:</b>", styles['Normal']), # Moved to left
         Paragraph(f"{job_details.get('required_qty', 0.0):,.2f}", styles['Normal']),
         "", ""] # Empty cells for the right side
    ]

    header_table = Table(header_data, colWidths=[1.2*inch, 3.8*inch, 1.2*inch, 3.8*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('SPAN', (1, -1), (3, -1)), # Span the second cell of the last row
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.25*inch))


    # --- Main Component Table ---
    # ... (Component table data and style remains the same) ...
    header_style_center = ParagraphStyle(name='HeaderCenter', fontSize=9, fontName='Helvetica-Bold', alignment=TA_CENTER)
    table_headers = [
        Paragraph("Part", header_style_center),
        Paragraph("Part Description", header_style_center),
        Paragraph("Lot #", header_style_center),
        Paragraph("Exp Date", header_style_center),
        Paragraph("Starting Lot Qty", header_style_center),
        Paragraph("Ending Inventory", header_style_center),
        Paragraph("Packaged Qty", header_style_center),
        Paragraph("Yield Cost/Scrap", header_style_center),
        Paragraph("Yield Loss", header_style_center)
    ]
    col_widths = [
        1.0*inch, 2.5*inch, 1.2*inch, 0.8*inch,
        1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch, 0.5*inch
    ]
    table_data = [table_headers]
    table_styles = [
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
        ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),
        ('LEFTPADDING', (4, 1), (-1, -1), 6),
        ('RIGHTPADDING', (4, 1), (-1, -1), 6),
    ]
    current_row = 1
    if not job_details.get('grouped_list'):
        table_data.append([
            Paragraph("No component transactions found for this job.", styles['Normal']),
            "", "", "", "", "", "", "", ""
        ])
        table_styles.append(('SPAN', (0, 1), (-1, 1)))
    else:
        for part_num, group in job_details.get('grouped_list', {}).items():
            num_lots = len(group['lots'])
            if num_lots == 0:
                continue
            start_row = current_row
            end_row = current_row + num_lots - 1
            if num_lots > 1:
                table_styles.append(('SPAN', (0, start_row), (0, end_row)))
                table_styles.append(('SPAN', (1, start_row), (1, end_row)))
            table_styles.append(('VALIGN', (0, start_row), (1, end_row), 'MIDDLE'))
            for i, lot_summary in enumerate(group['lots']):
                part_cell_text = part_num if i == 0 else ""
                desc_cell_text = group.get('part_description', 'N/A') if i == 0 else ""
                part_cell = Paragraph(part_cell_text, styles['Normal'])
                desc_cell = Paragraph(desc_cell_text, styles['Normal'])
                lot_cell = Paragraph(lot_summary.get('lot_number', 'N/A'), styles['Normal'])
                exp_cell = Paragraph(lot_summary.get('exp_date', 'N/A'), styles['Normal'])
                part_cell.style.alignment = TA_CENTER
                desc_cell.style.alignment = TA_LEFT
                lot_cell.style.alignment = TA_CENTER
                exp_cell.style.alignment = TA_CENTER
                row_data = [
                    part_cell,
                    desc_cell,
                    lot_cell,
                    exp_cell,
                    f"{lot_summary.get('Starting Lot Qty', 0.0):,.2f}",
                    f"{lot_summary.get('Ending Inventory', 0.0):,.2f}",
                    f"{lot_summary.get('Packaged Qty', 0.0):,.2f}",
                    f"{lot_summary.get('Yield Cost/Scrap', 0.0):,.2f}",
                    f"{lot_summary.get('Yield Loss', 0.0):.2f}%"
                ]
                table_data.append(row_data)
                current_row += 1
    component_table = Table(table_data, colWidths=col_widths)
    component_table.setStyle(TableStyle(table_styles))
    story.append(component_table)

    # --- Add "Report Generated" date ---
    story.append(Spacer(1, 0.2*inch))
    gen_style = ParagraphStyle(name='GenStyle', fontSize=9, alignment=TA_RIGHT)
    story.append(Paragraph(f"Report Generated: {datetime.now().strftime('%m/%d/%Y %I:%M %p')}", gen_style))

    # Build the PDF
    doc.build(story, onFirstPage=_header_footer_layout, onLaterPages=_header_footer_layout)

    buffer.seek(0)
    filename = f"CoC_{job_details.get('job_number', '000000000')}.pdf"

    return buffer, filename