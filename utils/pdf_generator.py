# utils/pdf_generator.py
"""
Utility to generate PDF reports, starting with the CoC Report.
MODIFIED: Further reduced spacing after the main table and adjusted
          compliance text font size/leading to encourage fitting on one page.
MODIFIED: Signature block and Statement remain at the end of the story.
MODIFIED: Header function only contains logo and address.
MODIFIED: Adjusted top/bottom margins.
ADDED: UoM, Shelf Life, Batch Number, PO Number to Header Info Table.
ADDED: UoM to Component Detail Table.
Adjusted layouts and column widths.
REVISED: Header table layout for better readability and alignment.
FIXED: Handle potential NoneType error during PDF generation.
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

    def _header_layout(canvas, doc):
        """Draws the custom header (logo, address)"""
        # ... (Header layout code remains unchanged from the previous version) ...
        canvas.saveState()

        page_width = doc.width + doc.leftMargin + doc.rightMargin
        page_height = doc.height + doc.topMargin + doc.bottomMargin

        # === Logo and Address (Top Part) ===
        address_top_y = page_height - 0.5*inch
        canvas.setFont('Helvetica', 9)
        canvas.drawRightString(page_width - doc.rightMargin, address_top_y, "2745 HUNTINGTON DRIVE")
        address_next_y = address_top_y - 0.16*inch
        canvas.drawRightString(page_width - doc.rightMargin, address_next_y, "DUARTE, CALIFORNIA 91010")

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

        canvas.restoreState()


    # --- Document Setup ---
    buffer = io.BytesIO()
    # **** ADJUSTED MARGINS ****
    adjusted_top_margin = 1.3 * inch
    adjusted_bottom_margin = 0.6 * inch # Slightly smaller again
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=0.5*inch, leftMargin=0.5*inch,
                            topMargin=adjusted_top_margin,
                            bottomMargin=adjusted_bottom_margin)

    # --- Story Building ---
    story = []
    styles = getSampleStyleSheet()
    multiline_style = ParagraphStyle(name='MultiLine', parent=styles['Normal'], leading=12)
    numeric_style_right = ParagraphStyle(name='NumericRight', parent=styles['Normal'], alignment=TA_RIGHT)
    numeric_style_left = ParagraphStyle(name='NumericLeft', parent=styles['Normal'], alignment=TA_LEFT)

    # --- Title ---
    title_style = ParagraphStyle(name='TitleStyle', fontSize=16, alignment=TA_CENTER, fontName='Helvetica-Bold')
    story.append(Paragraph("SALEABLE PRODUCT CERTIFICATE OF COMPLIANCE", title_style))
    story.append(Spacer(1, 0.25*inch))

    # --- Header Info Table --- (No changes needed)
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

    header_data_revised = [
        [Paragraph("<b>Job Number:</b>", styles['Normal']), Paragraph(job_number_val, styles['Normal']), Paragraph("<b>Customer:</b>", styles['Normal']), Paragraph(customer_val, multiline_style)],
        [Paragraph("<b>Part Number:</b>", styles['Normal']), Paragraph(part_number_val, styles['Normal']), Paragraph("<b>Sales Order:</b>", styles['Normal']), Paragraph(sales_order_val, styles['Normal'])],
        [Paragraph("<b>UoM:</b>", styles['Normal']), Paragraph(uom_val, styles['Normal']), Paragraph("<b>PO Number:</b>", styles['Normal']), Paragraph(po_number_val, styles['Normal'])],
        [Paragraph("<b>Part Description:</b>", styles['Normal']), Paragraph(part_desc_val, multiline_style), "", ""],
        [Paragraph("<b>Required Qty:</b>", styles['Normal']), Paragraph(req_qty_val, numeric_style_left), Paragraph("<b>Shelf Life:</b>", styles['Normal']), Paragraph(shelf_life_text, multiline_style)],
        [Paragraph("<b>Completed Qty:</b>", styles['Normal']), Paragraph(comp_qty_val, numeric_style_left), Paragraph("<b>Batch Number:</b>", styles['Normal']), Paragraph(batch_number_text, multiline_style)],
    ]
    header_col_widths_revised = [1.3*inch, 3.7*inch, 1.3*inch, 3.7*inch]
    header_table_revised = Table(header_data_revised, colWidths=header_col_widths_revised)
    header_table_revised.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6), ('SPAN', (1, 3), (3, 3)),
        ('RIGHTPADDING', (0, 0), (0, -1), 10), ('RIGHTPADDING', (2, 0), (2, -1), 10),
    ]))
    story.append(header_table_revised)
    story.append(Spacer(1, 0.25*inch))

    # --- Main Component Table --- (No changes needed)
    header_style_center = ParagraphStyle(name='HeaderCenter', fontSize=9, fontName='Helvetica-Bold', alignment=TA_CENTER)
    header_style_left = ParagraphStyle(name='HeaderLeft', fontSize=9, fontName='Helvetica-Bold', alignment=TA_LEFT)
    body_style_center = ParagraphStyle(name='BodyCenter', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)
    body_style_left = ParagraphStyle(name='BodyLeft', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT)
    table_headers = [
        Paragraph("Part", header_style_left), Paragraph("Part Description", header_style_left), Paragraph("UoM", header_style_center),
        Paragraph("Lot #", header_style_center), Paragraph("Exp Date", header_style_center), Paragraph("Starting Lot Qty", header_style_center),
        Paragraph("Ending Inventory", header_style_center), Paragraph("Packaged Qty", header_style_center), Paragraph("Yield Cost/Scrap", header_style_center),
        Paragraph("Yield Loss", header_style_center)
    ]
    col_widths = [ 0.9*inch, 2.0*inch, 0.5*inch, 1.1*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch, 0.5*inch ]
    table_data = [table_headers]
    table_styles = [
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), ('GRID', (0,0), (-1,-1), 1, colors.black), ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (2,1), (-1,-1), 'CENTER'), ('ALIGN', (0,1), (1,-1), 'LEFT'), ('FONTSIZE', (0,1), (-1,-1), 9),
    ]
    current_row = 1
    if not job_details.get('grouped_list'):
        table_data.append([ Paragraph("No component transactions found for this job.", body_style_center)] + [""]*9)
        table_styles.append(('SPAN', (0, 1), (-1, 1)))
    else:
        for part_num, group in job_details.get('grouped_list', {}).items():
            num_lots = len(group['lots'])
            if num_lots == 0: continue
            start_row = current_row; end_row = current_row + num_lots - 1
            if num_lots > 1:
                table_styles.extend([('SPAN', (0, start_row), (0, end_row)), ('SPAN', (1, start_row), (1, end_row)), ('SPAN', (2, start_row), (2, end_row))])
            table_styles.append(('VALIGN', (0, start_row), (2, end_row), 'MIDDLE'))
            for i, lot_summary in enumerate(group['lots']):
                part_cell = Paragraph(part_num if i == 0 else "", body_style_left)
                desc_cell = Paragraph(group.get('part_description', 'N/A') if i == 0 else "", body_style_left)
                uom_cell = Paragraph(group.get('unit_of_measure', 'N/A') if i == 0 else "", body_style_center)
                lot_cell = Paragraph(lot_summary.get('lot_number', 'N/A'), body_style_center)
                exp_cell = Paragraph(lot_summary.get('exp_date', 'N/A'), body_style_center)
                start_qty_str = f"{lot_summary.get('Starting Lot Qty', 0.0):,.2f}"
                end_inv_str = f"{lot_summary.get('Ending Inventory', 0.0):,.2f}"
                pkg_qty_str = f"{lot_summary.get('Packaged Qty', 0.0):,.2f}"
                yield_cost_str = f"{lot_summary.get('Yield Cost/Scrap', 0.0):,.2f}"
                yield_loss_str = f"{lot_summary.get('Yield Loss', 0.0):.2f}%"
                table_data.append([ part_cell, desc_cell, uom_cell, lot_cell, exp_cell, start_qty_str, end_inv_str, pkg_qty_str, yield_cost_str, yield_loss_str ])
                current_row += 1
    component_table = Table(table_data, colWidths=col_widths)
    component_table.setStyle(TableStyle(table_styles))
    story.append(component_table)

    # **** Statement and Signature Block TOGETHER at END of story ****
    # **** FURTHER REDUCED SPACING and FONT SIZE ****
    story.append(Spacer(1, 0.1*inch)) # Very small space before the statement

    statement_title_style = ParagraphStyle( name='FooterTitle', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=3) # Smaller font, less space
    # Smaller font size (7.5) and tighter leading (8.5)
    statement_body_style = ParagraphStyle( name='FooterBody', parent=styles['Normal'], fontSize=7.5, fontName='Helvetica', alignment=TA_LEFT, leading=8.5, spaceAfter=6) # Less space after

    title_text = "Statement of Compliance:"
    body_text = (
        "This certifies that the subject material has been manufactured according to the relevant material Specifications and Standard Operating Procedures. "
        "That any deviations from standard specifications and procedures have been properly approved, documented, and reported above. "
        "That the material has been inspected and tested according to the specified quality requirements, and that it meets the specified requirements. "
        "That the manufacturing and quality assurance processes have been properly documented, and that the documents are available for review. "
        "That this product has not been altered, and no biological contamination has been introduced during the packaging process."
    )
    story.append(Paragraph(title_text, statement_title_style))
    story.append(Paragraph(body_text, statement_body_style))

    story.append(Spacer(1, 0.05*inch)) # Very small space before signature lines

    # Signature block using a Table (slightly smaller font)
    sig_style = ParagraphStyle(name='SigLabel', parent=styles['Normal'], fontSize=8.5, fontName='Helvetica-Bold') # Smaller font
    sig_data = [
        [Paragraph("Authorized Signature:", sig_style), "", Paragraph("Date:", sig_style), "", Paragraph("Title:", sig_style), ""]
    ]
    sig_table = Table(sig_data, colWidths=[1.4*inch, 2.1*inch, 0.4*inch, 1.4*inch, 0.4*inch, 1.9*inch])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('LINEBELOW', (1, 0), (1, 0), 1, colors.black), ('LINEBELOW', (3, 0), (3, 0), 1, colors.black), ('LINEBELOW', (5, 0), (5, 0), 1, colors.black),
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 1), # Reduced bottom padding
    ]))
    story.append(sig_table)
    # **** END STATEMENT/SIGNATURE BLOCK ****

    # Build the PDF
    doc.build(story, onFirstPage=_header_layout, onLaterPages=_header_layout, canvasmaker=PageNumCanvas)

    buffer.seek(0)
    filename = f"CoC_{job_details.get('job_number', '000000000')}.pdf"

    return buffer, filename

# Custom Canvas class to draw the page number footer
class PageNumCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont('Helvetica', 8)
        page_width, page_height = self._pagesize
        # Draw page number slightly lower to use reduced bottom margin
        self.drawCentredString(page_width / 2.0, 0.35 * inch, f"Page {self._pageNumber}") # Positioned slightly lower
        self.restoreState()