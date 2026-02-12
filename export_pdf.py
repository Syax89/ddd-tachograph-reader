import json
import sys
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def generate_pdf(json_data, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("Report Analisi Tachigrafo Digitale (v1.1.2)", styles['Title']))
    elements.append(Spacer(1, 12))

    # Metadata
    meta = json_data.get("metadata", {})
    elements.append(Paragraph(f"<b>File:</b> {meta.get('filename')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Generazione:</b> {meta.get('generation')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Stato Integrità:</b> {meta.get('integrity_check')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Data Analisi:</b> {meta.get('parsed_at')}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Driver & Vehicle
    driver = json_data.get("driver", {})
    vehicle = json_data.get("vehicle", {})
    elements.append(Paragraph(f"<b>Conducente (Card):</b> {driver.get('card_number')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Veicolo (Targa):</b> {vehicle.get('plate')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Veicolo (VIN):</b> {vehicle.get('vin')}", styles['Normal']))
    elements.append(Spacer(1, 18))

    # GNSS Locations (if any)
    locations = json_data.get("locations", [])
    if locations:
        elements.append(Paragraph("Posizioni GNSS Rilevate (G2/Smart)", styles['Heading2']))
        # Show last 5 locations
        loc_data = [["Timestamp", "Latitudine", "Longitudine", "Tipo"]]
        for loc in locations[:10]: # Limit to first 10 for space
            loc_data.append([loc.get("timestamp"), loc.get("latitude"), loc.get("longitude"), loc.get("type")])
        
        lt = Table(loc_data, colWidths=[120, 80, 80, 60])
        lt.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(lt)
        if len(locations) > 10:
            elements.append(Paragraph(f"... altre {len(locations)-10} posizioni omesse nel report cartaceo.", styles['Italic']))
        elements.append(Spacer(1, 18))

    # Infractions
    elements.append(Paragraph("Infrazioni Rilevate (UE 561/2006)", styles['Heading2']))
    infractions = json_data.get("infractions", [])
    if not infractions:
        elements.append(Paragraph("Nessuna infrazione rilevata.", styles['Normal']))
    else:
        data = [["Data", "Gravità", "Tipo", "Descrizione"]]
        for inf in infractions:
            severity = inf.get("severity", "SI")
            # Color coding for severity
            sev_p = Paragraph(f"<b>{severity}</b>", ParagraphStyle('sev', textColor=colors.red if severity=="MSI" else colors.orange if severity=="SI" else colors.black))
            data.append([inf.get("data"), sev_p, inf.get("tipo"), inf.get("descrizione")])
        
        t = Table(data, colWidths=[60, 40, 150, 210])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(t)
    elements.append(Spacer(1, 18))

    # Activities (Summary for the last 7 days available)
    elements.append(Paragraph("Riepilogo Attività Recenti", styles['Heading2']))
    activities = json_data.get("activities", [])
    for day in activities[:7]: # Show only last 7 days to keep PDF lean
        elements.append(Paragraph(f"Data: {day.get('data')} - Km: {day.get('km')}", styles['Heading3']))
        day_data = [["Ora", "Tipo", "Slot"]]
        for ev in day.get("eventi", []):
            day_data.append([ev.get("ora"), ev.get("tipo"), ev.get("slot")])
        
        dt = Table(day_data, colWidths=[80, 200, 100])
        dt.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(dt)
        elements.append(Spacer(1, 12))

    doc.build(elements)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 export_pdf.py input.json output.pdf")
    else:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            data = json.load(f)
        generate_pdf(data, sys.argv[2])
        print(f"PDF generato: {sys.argv[2]}")
