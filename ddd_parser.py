import struct
import os
import json
from datetime import datetime, timezone

class TachoParser:
    """
    Professional analysis engine for Tachograph files (.DDD).
    Implements TLV structural decoding and binary parsing of standard records.
    Refactored to remove regex dependencies for core fields and optimize activity extraction.
    """
    
    TAGS = {
        0x0001: "EF_Vehicle_Identification", # For VU Files
        0x0002: "EF_ICC",
        0x0005: "EF_IC",
        0x0006: "EF_Application_Identification",
        0x0501: "EF_Card_Certificate",
        0x0502: "EF_Identification",
        0x0503: "EF_Driving_Licence_Info",
        0x0504: "EF_Events_Data",
        0x0505: "EF_Faults_Data",
        0x0506: "EF_Driver_Activity_Data",
        0x0507: "EF_Vehicles_Used",
        0x0508: "EF_Places",
        0x0509: "EF_Current_Usage",
        0x050A: "EF_Control_Activity_Data",
        0x050B: "EF_Specific_Conditions",
        0x0201: "EF_Identification_G2",
        0x0206: "EF_Activity_G2",
    }

    def __init__(self, file_path):
        self.file_path = file_path
        self.raw_data = None
        self.results = {
            "metadata": {
                "filename": os.path.basename(file_path),
                "generation": "Unknown",
                "parsed_at": datetime.now().isoformat()
            },
            "driver": {"card_number": "N/A"},
            "vehicle": {"vin": "N/A", "plate": "N/A"},
            "activities": []
        }

    def _decode_string(self, data):
        """Decode binary string data using latin-1 and strip padding."""
        return data.decode('latin-1', errors='ignore').strip()

    def _decode_activity_val(self, val):
        """Decode a 2-byte activity value based on Annex 1B/1C standards."""
        # Standard G1 Activity Change Info (2 bytes):
        # Bit 15: slot (0=First, 1=Second)
        # Bit 14: driving status (0=Single, 1=Crew)
        # Bit 13: card status (0=Inserted, 1=Not inserted)
        # Bit 11-12: activity (0=Break, 1=Availability, 2=Work, 3=Driving)
        # Bit 0-10: minutes since midnight
        slot = (val >> 15) & 1
        act_code = (val >> 11) & 3 
        mins = val & 0x07FF 
        
        acts = {0: "RIPOSO", 1: "DISPONIBILITÀ", 2: "LAVORO", 3: "GUIDA"}
        return {
            "tipo": acts.get(act_code, "SCONOSCIUTO"),
            "ora": f"{mins // 60:02d}:{mins % 60:02d}",
            "slot": "Secondo" if slot else "Primo"
        }

    def _parse_identification(self, data, is_g2=False):
        """
        Parses EF_Identification (0x0502 or 0x0201).
        Supports both Driver Card and Vehicle Unit (VU) identification structures.
        """
        if len(data) < 17:
            return

        # Case 1: Driver Card Identification
        # G1/G2 Card Identification starts with cardIssuingMemberState (1 byte)
        # followed by cardNumber (18 bytes for G1, 18 bytes for G2)
        # We try to detect if it's a card number (usually starts with a letter or digit)
        card_num = self._decode_string(data[1:17])
        if card_num and (card_num[0].isalnum()):
             self.results["driver"]["card_number"] = card_num

        # Case 2: Vehicle Unit Identification (if 0x0502 is used for VU records)
        # VU G1 Vehicle Identification: VIN (17) + Nation (1) + Plate (14)
        # We check if the first 17 bytes look like a VIN
        vin_candidate = self._decode_string(data[0:17])
        if len(vin_candidate) == 17 and vin_candidate.isalnum():
            self.results["vehicle"]["vin"] = vin_candidate
            # If there's enough data for Plate
            if len(data) >= 17 + 1 + 14:
                # Plate is at offset 18 (1 byte Nation + 1 byte CodePage + 13 bytes string)
                plate = self._decode_string(data[19:19+13])
                if plate:
                    self.results["vehicle"]["plate"] = plate

    def _parse_vehicles_used(self, data):
        """Parses EF_Vehicles_Used (0x0507) to extract VIN and Plate from Card data."""
        # 0x0507 Record (G1): 
        #   vehicleFirstUse (4), vehicleLastUse (4), 
        #   vehicleRegistrationNation (1), vehicleRegistrationNumber (14),
        #   vuDataBlockCounter (2) = 23 bytes (standard says 23 or 25 depending on alignment)
        # Actually 4+4+1+14+2 = 25 bytes.
        if len(data) < 27: return # 2 (count) + 25 (first record)
        
        try:
            num_records = struct.unpack(">H", data[0:2])[0]
            if num_records > 0:
                ptr = 2
                # Most recent vehicle is usually the first in the list
                vrm_raw = data[ptr+9 : ptr+9+14]
                if len(vrm_raw) > 1:
                    # vrm_raw[0] is CodePage, vrm_raw[1:] is Plate
                    plate = self._decode_string(vrm_raw[1:])
                    if plate:
                        self.results["vehicle"]["plate"] = plate
        except Exception:
            pass

    def parse(self):
        if not os.path.exists(self.file_path): return None
        with open(self.file_path, 'rb') as f:
            self.raw_data = f.read()

        # Simple generation detection
        if self.raw_data.startswith(b'\x76\x21'):
            self.results["metadata"]["generation"] = "G2 (Smart)"
        else:
            self.results["metadata"]["generation"] = "G1 (Digital)"

        pos = 0
        while pos + 5 <= len(self.raw_data):
            try:
                tag = struct.unpack(">H", self.raw_data[pos:pos+2])[0]
                # byte pos+2 is type (ignored for now)
                length = struct.unpack(">H", self.raw_data[pos+3:pos+5])[0]
                
                if tag in self.TAGS and length <= (len(self.raw_data) - (pos + 5)):
                    val = self.raw_data[pos+5 : pos+5+length]
                    
                    if tag == 0x0502: # EF_Identification (G1)
                        self._parse_identification(val)
                    
                    elif tag == 0x0001: # EF_Vehicle_Identification (VU)
                        self._parse_identification(val) # Reuse logic for VIN/Plate

                    elif tag == 0x0201: # EF_Identification_G2
                        self._parse_identification(val, is_g2=True)

                    elif tag == 0x0507: # EF_Vehicles_Used
                        self._parse_vehicles_used(val)

                    elif tag == 0x0506: # EF_Driver_Activity_Data
                        self._parse_activities(val, length)

                    pos += 5 + length
                    continue
            except Exception:
                pass
            pos += 1

        # Fallback for VIN if not found in structured data (often at fixed offset in VU files)
        # If still N/A and it looks like a VU file, we could check other tags.
        # But per requirements, we avoid regex. 
        # In a VU file, VIN is usually at a specific record (e.g. Tag 0x0001)
        # Let's check for Tag 0x0001 or 0x0021 which often contains Vehicle Identification in VU downloads.
        
        return self.results

    def _parse_activities(self, val, length):
        """
        Optimized parsing of EF_Driver_Activity_Data (0x0506).
        Extracts ALL activities for each daily record.
        """
        ptr = 4 # Skip some header bytes (standard varies slightly by card)
        while ptr + 14 <= length:
            try:
                # G1 Record Structure:
                # offset 0: previousRecordLength (2)
                # offset 2: recordLength (2)
                # offset 4: recordDate (4)
                # offset 8: dailyPresenceCounter (2)
                # offset 10: dayDistance (2)
                # offset 12+: activityChangeInfo (2 each)
                
                rec_len = struct.unpack(">H", val[ptr+2:ptr+4])[0]
                if rec_len < 12 or ptr + rec_len > length:
                    ptr += 28 # Fallback to fixed step if record length seems invalid
                    continue
                    
                ts = struct.unpack(">I", val[ptr+4:ptr+8])[0]
                # Validate timestamp (roughly between 2010 and 2030)
                if 1262304000 < ts < 1893456000:
                    dist = struct.unpack(">H", val[ptr+10:ptr+12])[0]
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%d/%m/%Y')
                    daily = {"data": dt, "km": dist, "eventi": []}
                    
                    # Extract ALL activity events in this record
                    for i in range(12, rec_len, 2):
                        if ptr + i + 2 <= length:
                            ev_val = struct.unpack(">H", val[ptr+i:ptr+i+2])[0]
                            # 0x0000 or 0xFFFF are usually padding/end
                            if ev_val != 0 and ev_val != 0xFFFF:
                                daily["eventi"].append(self._decode_activity_val(ev_val))
                    
                    self.results["activities"].append(daily)
                
                ptr += rec_len
            except Exception:
                ptr += 28

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(TachoParser(sys.argv[1]).parse(), indent=2))
