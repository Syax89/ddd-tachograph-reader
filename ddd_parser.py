import struct
import os
import re
import json
from datetime import datetime, timezone

class TachoParser:
    """
    Motore di analisi professionale per file Tachigrafo (.DDD).
    Supporta Generazione 1 (Digital) e Generazione 2 (Smart).
    """
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.raw_data = None
        self.content_latin = ""
        self.results = {
            "metadata": {
                "filename": os.path.basename(file_path),
                "generation": "Unknown",
                "parsed_at": datetime.now().isoformat()
            },
            "vehicle": {
                "vin": "Non rilevato",
                "plate": "Non rilevata",
            },
            "driver": {
                "card_number": "Non rilevato",
                "names": [],
            },
            "trips": []
        }

    def _load_file(self):
        if not os.path.exists(self.file_path):
            return False
        with open(self.file_path, 'rb') as f:
            self.raw_data = f.read()
        self.content_latin = self.raw_data.decode('latin-1', errors='ignore')
        return True

    def _detect_generation(self):
        if self.raw_data.startswith(b'\x76\x21'):
            self.results["metadata"]["generation"] = "G2 (Smart Tachograph)"
        else:
            self.results["metadata"]["generation"] = "G1 (Digital Tachograph)"

    def _extract_basic_info(self):
        # VIN (17 caratteri)
        vin_match = re.search(r'[A-Z0-9]{17}', self.content_latin)
        if vin_match:
            self.results["vehicle"]["vin"] = vin_match.group(0)
            
        # Numero Carta (Pattern I + numeri)
        card_match = re.search(r'[A-Z][0-9]{14,16}', self.content_latin)
        if card_match:
            self.results["driver"]["card_number"] = card_match.group(0)

        # Targa (Heuristic)
        vrm_match = re.search(r'[A-Z]{2}[0-9]{3}[A-Z]{2}', self.content_latin)
        if vrm_match:
            self.results["vehicle"]["plate"] = vrm_match.group(0)

    def _extract_trips(self):
        """Estrae la cronologia dei viaggi dai record di utilizzo veicolo."""
        trips_seen = set()
        # Scansione record da 29 byte (Struttura: TS1(4), TS2(4), Nation(1), Plate(13), OdoStart(3), OdoEnd(3))
        for i in range(len(self.raw_data) - 29):
            try:
                ts1, ts2 = struct.unpack(">II", self.raw_data[i:i+8])
                # Filtro date plausibili (2020 - 2030)
                if 1577836800 < ts1 < 1893456000 and 1577836800 < ts2 < 1893456000 and ts2 >= ts1:
                    plate = self.raw_data[i+9 : i+22].decode('latin-1', errors='ignore').strip()
                    if re.match(r'[A-Z0-9]{5,10}', plate):
                        km_start = int.from_bytes(self.raw_data[i+23:i+26], 'big')
                        km_end = int.from_bytes(self.raw_data[i+26:i+29], 'big')
                        
                        if 0 < km_start < 1000000 and 0 < km_end < 1000000 and km_end >= km_start:
                            trip_id = (ts1, ts2, plate, km_start)
                            if trip_id not in trips_seen:
                                self.results["trips"].append({
                                    "data": datetime.fromtimestamp(ts1, tz=timezone.utc).strftime('%d/%m/%Y'),
                                    "inizio": datetime.fromtimestamp(ts1, tz=timezone.utc).strftime('%H:%M'),
                                    "fine": datetime.fromtimestamp(ts2, tz=timezone.utc).strftime('%H:%M'),
                                    "targa": plate,
                                    "km_inizio": km_start,
                                    "km_fine": km_end,
                                    "distanza": km_end - km_start
                                })
                                trips_seen.add(trip_id)
            except:
                continue
        
        # Ordina per data decrescente
        self.results["trips"].sort(key=lambda x: (x["data"], x["inizio"]), reverse=True)

    def parse(self):
        if not self._load_file():
            return None
        self._detect_generation()
        self._extract_basic_info()
        self._extract_trips()
        return self.results

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        parser = TachoParser(sys.argv[1])
        print(json.dumps(parser.parse(), indent=2, ensure_ascii=False))
