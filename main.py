"""
DDD Tachograph Reader - CLI Entry Point
"""
import argparse
import json
import sys
import logging
from ddd_parser import DDDParser


def main():
    parser = argparse.ArgumentParser(description="DDD Tachograph File Reader - Structural TLV Parser")
    parser.add_argument("file", help="Percorso del file .ddd da leggere")
    parser.add_argument("-o", "--output", help="Percorso del file JSON di output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Output verboso (debug TLV)")
    parser.add_argument("--tlv-dump", action="store_true", help="Mostra solo i blocchi TLV trovati")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s"
    )

    ddd = DDDParser(args.file)
    result = ddd.parse()

    if result is None:
        print("Errore durante il parsing del file.", file=sys.stderr)
        sys.exit(1)

    if args.tlv_dump:
        print(f"File: {args.file}")
        print(f"Generazione: {result['metadata']['generation']}")
        print(f"Blocchi TLV trovati: {result['metadata']['tlv_blocks_found']}")
        for tag_info in result['metadata']['tlv_tags']:
            print(f"  {tag_info}")
        sys.exit(0)

    output_json = json.dumps(result, indent=4, ensure_ascii=False)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"Dati salvati in {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
