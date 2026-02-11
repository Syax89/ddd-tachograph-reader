import struct
import os

class DDDParser:
    TAGS = {
        0x0002: "Card ICC Identification",
        0x0005: "Driver Card Holder Identification",
        0x0006: "Card Application Identification",
        0x0201: "Driver Card Identification",
        0x0202: "Card Download",
        0x0203: "Driving Licence Information",
        0x0204: "Events Data",
        0x0205: "Faults Data",
        0x0206: "Driver Activity Data",
        0x0207: "Vehicles Used Data",
        0x0208: "Places Data",
        0x0209: "Current Usage Data",
        0x020A: "Control Activity Data",
        0x020B: "Specific Conditions Data",
    }

    def __init__(self, file_path):
        self.file_path = file_path
        self.results = {"filename": os.path.basename(file_path), "sections": []}

    def parse(self):
        if not os.path.exists(self.file_path): return None
        with open(self.file_path, 'rb') as f:
            data = f.read()
        
        offset = 0
        while offset < len(data) - 4:
            # Cerchiamo i tag noti
            tag = struct.unpack_from(">H", data, offset)[0]
            if tag in self.TAGS:
                # In G1, dopo il tag c'è spesso un byte 00 o 01 e poi la lunghezza
                # Proviamo a vedere se a offset+3 o offset+2 c'è la lunghezza
                length = struct.unpack_from(">H", data, offset + 3)[0]
                
                # Se la lunghezza sembra valida
                if length > 0 and (offset + 5 + length) <= len(data):
                    section_data = data[offset + 5 : offset + 5 + length]
                    info = {
                        "tag": hex(tag),
                        "name": self.TAGS[tag],
                        "length": length,
                        "offset": offset
                    }
                    if tag == 0x0005: # Driver Identification
                        info["details"] = {"raw_name": section_data[1:36].decode('latin-1', errors='ignore').strip()}
                    
                    self.results["sections"].append(info)
                    offset += 5 + length
                    continue
            offset += 1
        return self.results

if __name__ == "__main__":
    import sys, json
    if len(sys.argv) > 1:
        print(json.dumps(DDDParser(sys.argv[1]).parse(), indent=2))
