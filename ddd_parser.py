import struct
import os

class DDDParser:
    """
    Parser minimale per file DDD (Tachigrafo Digitale).
    Basato sulle specifiche Annex 1B / ISO 16844-7.
    """
    
    TAGS = {
        0x0001: "Card ICC Identification",
        0x0002: "Card Chip Identification",
        0x0005: "Driver Card Holder Identification",
        0x0006: "Card Application Identification",
        0x0007: "Card Certificate",
        0x0008: "Member State Certificate",
        0x0009: "Card Identification",
        0x000A: "Card Download",
        0x000B: "Driving Licence Information",
        0x000C: "Events Data",
        0x000D: "Faults Data",
        0x000E: "Driver Activity Data",
        0x000F: "Vehicles Used Data",
        0x0010: "Places Data",
        0x0011: "Current Usage Data",
        0x0012: "Control Activity Data",
        0x0013: "Specific Conditions Data",
        0x0014: "Vehicle Unit Identification",
        0x0015: "Vehicle Unit Calibration",
        0x0016: "Vehicle Unit Events",
        0x0017: "Vehicle Unit Faults",
        0x0018: "Vehicle Unit Activity",
        0x0019: "Vehicle Unit Speed",
        0x001A: "Vehicle Unit Places",
    }

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.results = {
            "filename": os.path.basename(file_path),
            "file_size": 0,
            "sections": []
        }

    def parse(self):
        if not os.path.exists(self.file_path):
            return None
            
        with open(self.file_path, 'rb') as f:
            self.data = f.read()
            self.results["file_size"] = len(self.data)

        offset = 0
        while offset < len(self.data) - 3:
            try:
                # Struttura TLV (Tag-Length-Value)
                # In molti file DDD, il tag è 2 byte e la lunghezza è 2 byte
                tag = struct.unpack_from(">H", self.data, offset)[0]
                length = struct.unpack_from(">H", self.data, offset + 2)[0]
                
                if length > (len(self.data) - offset - 4) or length == 0:
                    # Se la lunghezza è sospetta, proviamo a saltare di 1
                    offset += 1
                    continue
                
                section_name = self.TAGS.get(tag, f"Unknown Tag ({hex(tag)})")
                
                # Estrazione dati grezzi (per ora solo info base)
                section_data = self.data[offset + 4 : offset + 4 + length]
                
                info = {
                    "tag": hex(tag),
                    "name": section_name,
                    "length": length,
                    "offset": offset
                }
                
                # Esempio: Estrazione nome se è DriverCardHolderIdentification
                if tag == 0x0005:
                    try:
                        # Il nome inizia solitamente dopo alcuni byte di header
                        name_raw = section_data[1:36].decode('latin-1').strip()
                        info["details"] = {"driver_name": name_raw}
                    except:
                        pass

                self.results["sections"].append(info)
                offset += 4 + length
                
            except Exception:
                offset += 1
                
        return self.results

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        parser = DDDParser(sys.argv[1])
        print(parser.parse())
