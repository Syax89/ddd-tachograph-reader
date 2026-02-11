import struct
import os
from datetime import datetime, timezone

class DDDDecoder:
    @staticmethod
    def time_real(b):
        if len(b) < 4: return None
        ts = struct.unpack(">I", b[:4])[0]
        if ts == 0 or ts == 0xFFFFFFFF: return None
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    @staticmethod
    def string(b):
        return b.decode('latin-1', errors='ignore').strip()

    @staticmethod
    def card_number(b):
        if len(b) < 16: return None
        return b[:16].decode('latin-1', errors='ignore').strip()

    @staticmethod
    def vehicle_registration(b):
        if len(b) < 14: return {}
        return {
            "nation": hex(b[0]),
            "vrm": b[1:14].decode('latin-1', errors='ignore').strip()
        }

class DDDParser:
    # Mappa completa dei Tag Annex 1B (G1 e G2)
    TAGS = {
        # File Conducente
        0x0002: ("Card ICC Identification", "decode_icc"),
        0x0005: ("Driver Card Holder Identification", "decode_driver_names"),
        0x0201: ("Driver Card Identification", "decode_card_id"),
        0x0202: ("Card Download", "decode_generic"),
        0x0203: ("Driving Licence Information", "decode_licence"),
        0x0204: ("Events Data", "decode_generic"),
        0x0205: ("Faults Data", "decode_generic"),
        0x0206: ("Driver Activity Data", "decode_activity"),
        0x0207: ("Vehicles Used Data", "decode_vehicles_used"),
        0x0208: ("Places Data", "decode_generic"),
        0x0209: ("Current Usage Data", "decode_generic"),
        0x020A: ("Control Activity Data", "decode_generic"),
        0x020B: ("Specific Conditions Data", "decode_generic"),
        
        # File Veicolo (VU)
        0x0014: ("Vehicle Unit Identification", "decode_vu_id"),
        0x0015: ("Vehicle Unit Calibration", "decode_generic"),
        0x0016: ("Vehicle Unit Events", "decode_generic"),
        0x0017: ("Vehicle Unit Faults", "decode_generic"),
        0x0018: ("Vehicle Unit Activity", "decode_generic"),
        0x0019: ("Vehicle Unit Speed", "decode_generic"),
        0x001A: ("Vehicle Unit Places", "decode_generic"),
    }

    def __init__(self, file_path):
        self.file_path = file_path
        self.results = {
            "filename": os.path.basename(file_path),
            "parsed_at": datetime.now().isoformat(),
            "generation": "Unknown",
            "data": {}
        }

    def decode_generic(self, b):
        return {"raw_size": len(b), "hex_preview": b[:16].hex().upper()}

    def decode_icc(self, b):
        return {
            "clock_stop": hex(b[0]) if len(b) > 0 else None,
            "card_extended_serial": b[1:9].hex().upper() if len(b) > 8 else None,
            "card_approval_number": DDDDecoder.string(b[9:17]) if len(b) > 16 else None
        }

    def decode_driver_names(self, b):
        if len(b) < 78: return {}
        return {
            "surname": DDDDecoder.string(b[0:36]),
            "first_names": DDDDecoder.string(b[36:72]),
            "birth_date": DDDDecoder.time_real(b[72:76]),
            "preferred_language": DDDDecoder.string(b[76:78])
        }

    def decode_card_id(self, b):
        if len(b) < 60: return {}
        return {
            "card_number": DDDDecoder.card_number(b[1:17]),
            "issuing_state": hex(b[0]),
            "issue_date": DDDDecoder.time_real(b[25:29]),
            "expiry_date": DDDDecoder.time_real(b[33:37])
        }

    def decode_licence(self, b):
        if len(b) < 50: return {}
        return {
            "licence_number": DDDDecoder.string(b[2:18]),
            "issuing_state": hex(b[0])
        }

    def decode_vu_id(self, b):
        if len(b) < 80: return {}
        return {
            "manufacturer": DDDDecoder.string(b[0:36]),
            "vin": DDDDecoder.string(b[36:53]),
            "vrm": DDDDecoder.string(b[53:68])
        }

    def decode_vehicles_used(self, b):
        # Ogni record è circa 31 byte
        vehicles = []
        for i in range(0, len(b), 31):
            chunk = b[i:i+31]
            if len(chunk) < 31: break
            vehicles.append({
                "first_use": DDDDecoder.time_real(chunk[0:4]),
                "last_use": DDDDecoder.time_real(chunk[4:8]),
                "vrm": DDDDecoder.string(chunk[8:21])
            })
        return vehicles

    def decode_activity(self, b):
        # Analisi periodi di attività
        return {"raw_size": len(b), "info": "Dati attività giornaliere rilevati"}

    def parse(self):
        if not os.path.exists(self.file_path): return None
        with open(self.file_path, 'rb') as f:
            data = f.read()
        
        # Rilevamento Generazione (Heuristic)
        if data.startswith(b'\x76\x21'):
            self.results["generation"] = "G2 (Smart Tachograph)"
        else:
            self.results["generation"] = "G1 (Digital Tachograph)"

        offset = 0
        while offset < len(data) - 4:
            tag = struct.unpack_from(">H", data, offset)[0]
            if tag in self.TAGS:
                name, decoder_name = self.TAGS[tag]
                
                # Prova decodifica lunghezza (Annex 1B G1/G2 varia leggermente)
                length = struct.unpack_from(">H", data, offset + 3)[0]
                
                if length > 0 and (offset + 5 + length) <= len(data):
                    section_data = data[offset + 5 : offset + 5 + length]
                    decoder = getattr(self, decoder_name, self.decode_generic)
                    self.results["data"][name] = decoder(section_data)
                    offset += 5 + length
                    continue
            offset += 1
        return self.results

if __name__ == "__main__":
    import sys, json
    if len(sys.argv) > 1:
        print(json.dumps(DDDParser(sys.argv[1]).parse(), indent=2))
