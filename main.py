import argparse
import json
import os
import sys
from ddd_parser import DDDParser

def parse_ddd(file_path):
    """
    Legge un file DDD usando il parser nativo.
    """
    parser = DDDParser(file_path)
    return parser.parse()

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
    else:
        print("Errore durante il parsing.")

if __name__ == "__main__":
    main()
