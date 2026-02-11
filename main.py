import argparse
import json
import os
import sys

# Nota: Assicurati di aver installato tachoparser via:
# pip install git+https://github.com/traconiq/tachoparser.git

try:
    from tachoparser.ddd import DDD
except ImportError:
    print("Errore: tachoparser non trovato. Installa con:")
    print("pip install git+https://github.com/traconiq/tachoparser.git")
    sys.exit(1)

def parse_ddd(file_path):
    """
    Legge un file DDD e restituisce i dati parsati.
    """
    if not os.path.exists(file_path):
        print(f"Errore: Il file {file_path} non esiste.")
        return None

    try:
        with open(file_path, 'rb') as f:
            ddd = DDD(f.read())
            
        # Tachoparser restituisce oggetti complessi. 
        # Qui estraiamo le informazioni principali in un dizionario.
        data = {
            "filename": os.path.basename(file_path),
            "type": ddd.file_type,
            "sections": []
        }

        for section in ddd.sections:
            section_info = {
                "name": section.name,
                "tag": hex(section.tag) if hasattr(section, 'tag') else None,
                "size": len(section.data) if hasattr(section, 'data') else 0
            }
            data["sections"].append(section_info)

        return data
    except Exception as e:
        print(f"Errore durante il parsing: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="DDD Tachograph File Reader")
    parser.add_argument("file", help="Percorso del file .ddd da leggere")
    parser.add_argument("-o", "--output", help="Percorso del file JSON di output (opzionale)")
    
    args = parser.parse_args()

    result = parse_ddd(args.file)
    
    if result:
        output_json = json.dumps(result, indent=4)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output_json)
            print(f"Dati salvati in {args.output}")
        else:
            print(output_json)

if __name__ == "__main__":
    main()
