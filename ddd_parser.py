import struct
import os
import json
from datetime import datetime, timezone

class SignatureValidator:
    def validate_block(self, data, sig, pubkey, algorithm='RSA'):
        return True

class TachoParser:
    """
    Professional analysis engine for Tachograph files (.DDD).
    Version 3.0 - Handles G1 Card, G2 Card, and VU download formats.
    
    Key insights from real-world file analysis:
    - G1/G2 Card files use TAG(2)+TYPE(1)+LEN(2) TLV format
    - Activity data uses cyclic buffer with 2-byte pointers at offset 0-3
    - CardActivityDailyRecord: prevLen(2)+recLen(2)+date(4)+presence(2)+dist(2)+activities(N*2)
    - G2/VU files may embed activities within ASN.1 structures
    - Tag 0x0504 often contains activity data (not just 0x0506)
    - String fields use CodePage byte (first byte < 0x20 indicates encoding)
    """
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.raw_data = None
        self.validator = SignatureValidator()
        self.results = {
            "metadata": {
                "filename": os.path.basename(file_path),
                "generation": "Unknown",
                "parsed_at": datetime.now().isoformat(),
                "integrity_check": "Pending"
            },
            "driver": {"card_number": "N/A"},
            "vehicle": {"vin": "N/A", "plate": "N/A"},
            "activities": []
        }

    def _decode_string(self, data):
        """Decode binary string handling CodePage byte (Annex 1B/1C)."""
        if not data: return ""
        if data[0] < 0x20:
            encodings = {0x01: 'latin-1', 0x02: 'iso-8859-2', 0x03: 'iso-8859-3',
                         0x05: 'iso-8859-5', 0x06: 'iso-8859-6', 0x07: 'iso-8859-7',
                         0x08: 'iso-8859-8', 0x09: 'iso-8859-9', 0x0D: 'iso-8859-13',
                         0x0F: 'iso-8859-15', 0x10: 'iso-8859-16'}
            enc = encodings.get(data[0], 'latin-1')
            try:
                return data[1:].decode(enc, errors='ignore').strip().strip('\x00')
            except:
                return data[1:].decode('latin-1', errors='ignore').strip().strip('\x00')
        return data.decode('latin-1', errors='ignore').strip().strip('\x00')

    def _decode_activity_val(self, val):
        """Decode 2-byte activityChangeInfo (Annex 1B/1C)."""
        slot = (val >> 15) & 1
        crew = (val >> 14) & 1
        card = (val >> 13) & 1
        act_code = (val >> 11) & 3
        mins = val & 0x07FF
        if mins > 1440:
            mins = mins % 1440
        acts = {0: "RIPOSO", 1: "DISPONIBILITÀ", 2: "LAVORO", 3: "GUIDA"}
        return {
            "tipo": acts.get(act_code, "SCONOSCIUTO"),
            "ora": f"{mins // 60:02d}:{mins % 60:02d}",
            "slot": "Secondo" if slot else "Primo"
        }

    def _extract_card_number(self):
        """Scan entire file for card number pattern: Nation(1) + 16 alnum chars."""
        data = self.raw_data
        candidates = []
        for i in range(len(data) - 17):
            if not (0 < data[i] < 150): continue
            cand = data[i+1:i+17]
            if not all(0x20 <= c <= 0x7E for c in cand): continue
            s = cand.decode('latin-1').strip()
            if not (14 <= len(s) <= 16 and s[0].isalpha()): continue
            digit_count = sum(1 for c in s if c.isdigit())
            if digit_count < 10: continue
            # Skip if this is part of a VIN (17 alnum chars including the byte before)
            if i > 0 and (0x30 <= data[i] <= 0x39 or 0x41 <= data[i] <= 0x5A):
                # Check if data[i:i+17] is all uppercase alnum (VIN pattern)
                vin_cand = data[i:i+17]
                if all(0x30 <= c <= 0x39 or 0x41 <= c <= 0x5A for c in vin_cand):
                    continue  # Skip - it's part of a VIN
            # Also skip if followed by another alnum byte (making it 17+ chars = VIN)
            if i+17 < len(data) and (0x30 <= data[i+17] <= 0x39 or 0x41 <= data[i+17] <= 0x5A):
                continue
            candidates.append((digit_count, s))
        
        if candidates:
            # Prefer the candidate with the most digits (real card numbers are mostly digits)
            candidates.sort(key=lambda x: -x[0])
            self.results["driver"]["card_number"] = candidates[0][1]

    def _extract_plate(self):
        """Scan for vehicle registration: Nation(1) + CodePage(1) + Plate(13)."""
        data = self.raw_data
        plates_found = {}
        
        for i in range(len(data) - 15):
            nation = data[i]
            codepage = data[i+1]
            if not (0 < nation < 150 and codepage < 0x20): continue
            plate_raw = data[i+1:i+15]
            plate = self._decode_string(plate_raw)
            if not plate or len(plate) < 4 or len(plate) > 12: continue
            if not plate[0].isalpha(): continue
            if not any(c.isdigit() for c in plate): continue
            if not all(c.isalnum() for c in plate): continue
            # Count occurrences to find the most common plate
            plates_found[plate] = plates_found.get(plate, 0) + 1
        
        if plates_found:
            best = max(plates_found, key=plates_found.get)
            self.results["vehicle"]["plate"] = best

    def _extract_vin(self):
        """Scan for VIN: 17 uppercase alnum characters."""
        data = self.raw_data
        for i in range(len(data) - 17):
            cand = data[i:i+17]
            if all((0x30 <= c <= 0x39) or (0x41 <= c <= 0x5A) for c in cand):
                vin = cand.decode('latin-1')
                # VIN should not be all digits or all letters
                has_digit = any(c.isdigit() for c in vin)
                has_alpha = any(c.isalpha() for c in vin)
                if has_digit and has_alpha:
                    self.results["vehicle"]["vin"] = vin
                    return

    def _parse_cyclic_buffer_activities(self, val):
        """Parse CardActivityDailyRecord from cyclic buffer (standard G1/G2 format)."""
        if len(val) < 16: return
        
        oldest_ptr = struct.unpack(">H", val[0:2])[0]
        newest_ptr = struct.unpack(">H", val[2:4])[0]
        buf_size = len(val) - 4
        
        if newest_ptr >= buf_size or oldest_ptr >= buf_size:
            return  # Invalid pointers
        
        ptr = 4 + newest_ptr
        seen_dates = set()
        
        for _ in range(200):  # Max 200 days
            if ptr < 4 or ptr + 12 > len(val):
                break
            
            prev_len = struct.unpack(">H", val[ptr:ptr+2])[0]
            rec_len = struct.unpack(">H", val[ptr+2:ptr+4])[0]
            ts = struct.unpack(">I", val[ptr+4:ptr+8])[0]
            
            if rec_len < 14 or rec_len > 1000:
                break
            
            if not (1262304000 < ts < 1893456000):  # 2010-2030
                break
            
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            date_str = dt.strftime('%d/%m/%Y')
            
            if date_str in seen_dates:
                break
            seen_dates.add(date_str)
            
            pres = struct.unpack(">H", val[ptr+8:ptr+10])[0]
            dist = struct.unpack(">H", val[ptr+10:ptr+12])[0]
            
            daily = {"data": date_str, "km": dist, "eventi": []}
            
            for i in range(12, rec_len, 2):
                if ptr + i + 2 > len(val):
                    break
                ev_val = struct.unpack(">H", val[ptr+i:ptr+i+2])[0]
                if ev_val == 0 or ev_val == 0xFFFF:
                    continue
                daily["eventi"].append(self._decode_activity_val(ev_val))
            
            if daily["eventi"]:
                self.results["activities"].append(daily)
            
            if prev_len == 0:
                break
            
            # Navigate backwards in cyclic buffer
            ptr -= prev_len
            if ptr < 4:
                ptr += buf_size  # Wrap around
    
    def _scan_for_activity_sequences(self):
        """Fallback: scan entire file for monotonic activity sequences (for G2/VU files)."""
        data = self.raw_data
        if self.results["activities"]:  # Already have activities
            return
        
        runs = []
        i = 0
        while i < len(data) - 20:
            ev0 = struct.unpack('>H', data[i:i+2])[0]
            mins0 = ev0 & 0x07FF
            # Look for REST at 00:00 (common day start)
            if mins0 == 0 and (ev0 >> 11) & 3 == 0:
                # Try to read a sequence
                prev_mins = -1
                entries = []
                for j in range(0, min(600, len(data) - i), 2):
                    ev = struct.unpack('>H', data[i+j:i+j+2])[0]
                    if ev == 0 or ev == 0xFFFF:
                        break
                    mins = ev & 0x07FF
                    act = (ev >> 11) & 3
                    if mins <= 1440 and mins >= prev_mins:
                        entries.append(self._decode_activity_val(ev))
                        prev_mins = mins
                    else:
                        break
                
                if len(entries) >= 5:
                    # Try to find a date nearby (look for timestamp 4-50 bytes before)
                    date_str = "N/A"
                    for p in range(max(0, i-50), i):
                        ts = struct.unpack('>I', data[p:p+4])[0]
                        if 1577836800 < ts < 1893456000:
                            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                            # Prefer midnight timestamps
                            if dt.hour == 0 and dt.minute == 0:
                                date_str = dt.strftime('%d/%m/%Y')
                                break
                            date_str = dt.strftime('%d/%m/%Y')
                    
                    # Try to find distance nearby
                    dist = 0
                    
                    runs.append({
                        "data": date_str,
                        "km": dist,
                        "eventi": entries
                    })
                    i += len(entries) * 2
                    continue
            i += 2
        
        # Add unique days (deduplicate by date)
        seen = set()
        for run in runs:
            key = run["data"] + str(len(run["eventi"]))
            if key not in seen:
                seen.add(key)
                self.results["activities"].append(run)

    def parse(self):
        if not os.path.exists(self.file_path): return None
        with open(self.file_path, 'rb') as f:
            self.raw_data = f.read()

        self.results["metadata"]["generation"] = "G2 (Smart)" if self.raw_data.startswith(b'\x76\x21') else "G1 (Digital)"

        # Phase 1: Extract card number, plate, VIN via pattern scanning
        self._extract_card_number()
        self._extract_plate()
        self._extract_vin()

        # Phase 2: TLV-based activity extraction
        pos = 0
        while pos + 5 <= len(self.raw_data):
            try:
                tag = struct.unpack(">H", self.raw_data[pos:pos+2])[0]
                dtype = self.raw_data[pos+2]
                length = struct.unpack(">H", self.raw_data[pos+3:pos+5])[0]
                
                if length > (len(self.raw_data) - (pos + 5)) or length == 0:
                    pos += 1
                    continue

                val = self.raw_data[pos+5 : pos+5+length]
                
                # Try cyclic buffer parsing on large data blocks
                if tag in [0x0504, 0x0506, 0x0524, 0x0206] and length > 100:
                    if dtype in [0x00, 0x02]:  # Data blocks only (not signatures)
                        self._parse_cyclic_buffer_activities(val)

                pos += 5 + length
                continue
            except:
                pass
            pos += 1
        
        # Phase 3: Fallback - scan for activity sequences in G2/VU files
        if not self.results["activities"]:
            self._scan_for_activity_sequences()
        
        # Deduplicate activities by date+event count (Type 00/02 blocks may duplicate)
        seen = {}
        unique = []
        for act in self.results["activities"]:
            key = act["data"] + "_" + str(len(act["eventi"]))
            if key not in seen:
                seen[key] = True
                unique.append(act)
        self.results["activities"] = unique
        
        # Sort activities by date (newest first)
        self.results["activities"].sort(
            key=lambda x: datetime.strptime(x["data"], '%d/%m/%Y') if x["data"] != "N/A" else datetime.min,
            reverse=True
        )
        
        return self.results

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(TachoParser(sys.argv[1]).parse(), indent=2))
