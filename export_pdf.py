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

    # Titolo
    elements.append(Paragraph("Report Analisi Tachigrafo Digitale", styles['Title']))
    elements.append(Spacer(1, 12))

    # Metadati
    meta = json_data.get("metadata", {})
    elements.append(Paragraph(f"<b>File:</b> {meta.get('filename')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Generazione:</b> {meta.get('generation')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Stato Integrità:</b> {meta.get('integrity_check')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Data Analisi:</b> {meta.get('parsed_at')}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Conducente e Veicolo
    driver = json_data.get("driver", {})
    vehicle = json_data.get("vehicle", {})
    elements.append(Paragraph(f"<b>Conducente (Card):</b> {driver.get('card_number')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Veicolo (Targa):</b> {vehicle.get('plate')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Veicolo (VIN):</b> {vehicle.get('vin')}", styles['Normal']))
    elements.append(Spacer(1, 18))

    # Infrazioni
    elements.append(Paragraph("Infrazioni Rilevate (UE 561/2006)", styles['Heading2']))
    infractions = json_data.get("infractions", [])
    if not infractions:
        elements.append(Paragraph("Nessuna infrazione rilevata.", styles['Normal']))
    else:
        data = [["Data", "Tipo", "Descrizione"]]
        for inf in infractions:
            data.append([inf.get("data"), inf.get("tipo"), inf.get("descrizione")])
        
        t = Table(data, colWidths=[60, 150, 250])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(t)
    elements.append(Spacer(1, 18))

    # Attività
    elements.append(Paragraph("Log Attività Giornaliere", styles['Heading2']))
    activities = json_data.get("activities", [])
    for day in activities:
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
