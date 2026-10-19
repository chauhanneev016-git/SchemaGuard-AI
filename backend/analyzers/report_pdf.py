"""In-memory PDF report with ReportLab."""
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from xml.sax.saxutils import escape


def build_report_pdf(report, reviews):
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=42, rightMargin=42,
                                 topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    story = [Paragraph('SchemaGuard AI — Migration Impact Report', styles['Title']), Spacer(1, 12)]
    safe = lambda value: escape(str(value))
    story.append(Paragraph(f"Database: {safe(report['database'])} | Target: {safe(report['target_schema'])}", styles['Normal']))
    story.append(Paragraph(f"Generated: {safe(report['generated_at'])}", styles['Normal']))
    story.append(Spacer(1, 12))
    summary = report['summary']
    stats = [
        ['Registered queries', summary['total_queries']],
        ['Exact', summary['exact_match']], ['Semantic', summary['semantic_match']],
        ['Review required', summary['review_required']], ['Execution errors', summary['execution_errors']],
        ['Decision', summary['decision']],
    ]
    table = Table(stats, colWidths=[195, 265])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f1f0')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7), ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, -1), .4, colors.lightgrey),
    ]))
    story.extend([table, Spacer(1, 16)])
    story.append(Paragraph('Query-by-query findings', styles['Heading2']))
    for row in report['queries']:
        elements = [Paragraph(f"{safe(row['query_id'])}: {safe(row['query_name'])} — {safe(row['status'])}", styles['Heading3']),
                    Paragraph(safe(row['reason']), styles['Normal'])]
        for recommendation in row['recommendations']:
            elements.append(Paragraph('• ' + safe(recommendation), styles['Normal']))
        elements.append(Spacer(1, 9))
        story.append(KeepTogether(elements))
    story.append(Paragraph('Human review history', styles['Heading2']))
    if reviews:
        for entry in reviews[:30]:
            story.append(Paragraph(
                f"{safe(entry['created_at'])}: {safe(entry['query_id'])} — {safe(entry['decision'])}. "
                f"Reviewer: {safe(entry['reviewer'])}. Note: {safe(entry['note'])}", styles['Normal']))
    else:
        story.append(Paragraph('No review decisions recorded for this target.', styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph('Limitations', styles['Heading2']))
    for limitation in report['limitations']:
        story.append(Paragraph('• ' + safe(limitation), styles['Normal']))
    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()