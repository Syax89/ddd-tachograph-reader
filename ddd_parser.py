"""
DDD Tachograph Parser - Structural TLV Engine
==============================================
Parser strutturale per file .DDD (carte conducente) basato su lettura
sequenziale TLV (Tag-Length-Value) conforme a EU 165/2014 e 3821/85.

Supporta Generazione 1 (Digital) e Generazione 2 (Smart Tachograph).
"""

import struct
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Tag Registry ────────────────────────────────────────────────────────────
# Mappa dei File ID standard per carte conducente (EF sotto DF Tachograph)

DRIVER_CARD_TAGS = {
    0x0002: "EF_ICC",                        # Card ICC Identification
    0x0005: "EF_IC",                         # Card Chip Identification
    0x0006: "EF_Application_Identification", # Application ID
    0x0520: "EF_Card_Certificate",           # Card Certificate (G1)
    0x0521: "EF_CA_Certificate",             # CA Certificate (G1)
    0xC100: "EF_Card_Certificate",           # Card Certificate (G2)
    0xC101: "EF_CA_Certificate",             # CA Certificate (G2)
    0xC102: "EF_Link_Certificate",           # Link Certificate (G2)
    0x0502: "EF_Identification",             # Card Holder Identification
    0x0503: "EF_Driving_Licence_Info",       # Driving Licence Info
    0x0504: "EF_Events_Data",               # Events Data
    0x0505: "EF_Faults_Data",               # Faults Data
    0x0506: "EF_Driver_Activity_Data",       # Driver Activity Data
    0x0507: "EF_Vehicles_Used",              # Vehicles Used
    0x0508: "EF_Places",                     # Places (daily begin/end)
    0x0509: "EF_Current_Usage",              # Current Usage
    0x050A: "EF_Control_Activity_Data",      # Control Activity Data
    0x050B: "EF_Specific_Conditions",        # Specific Conditions
    # G2 additional
    0x0522: "EF_Card_MA_Certificate",
    0x0523: "EF_Card_Sign_Certificate",
    0x0524: "EF_VU_Certificate",
    # Varianti G2 con offset
    0x0201: "EF_Identification_G2",
    0x0202: "EF_Card_Download",
    0x0203: "EF_Driving_Licence_Info_G2",
    0x0204: "EF_Events_Data_G2",
    0x0205: "EF_Faults_Data_G2",
    0x0206: "EF_Driver_Activity_Data_G2",
    0x0207: "EF_Vehicles_Used_G2",
    0x0208: "EF_Places_G2",
    0x0209: "EF_Current_Usage_G2",
    0x020A: "EF_Control_Activity_Data_G2",
    0x020B: "EF_Specific_Conditions_G2",
}

# Activity codes (2-bit encoding in activity records)
ACTIVITY_CODES = {
    0: "RIPOSO",       # Rest / Break
    1: "DISPONIBILITÀ",  # Availability
    2: "LAVORO",       # Work (other)
    3: "GUIDA",        # Driving
}


# ── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class TLVBlock:
    """Singolo blocco TLV estratto dal file."""
    tag: int
    tag_name: str
    offset: int
    length: int
    value: bytes

    def __repr__(self):
        return f"<TLV 0x{self.tag:04X} '{self.tag_name}' offset={self.offset} len={self.length}>"


@dataclass
class DriverIdentification:
    card_number: str = ""
    card_issuing_member_state: str = ""
    card_issuing_authority: str = ""
    card_issue_date: Optional[datetime] = None
    card_validity_begin: Optional[datetime] = None
    card_expiry_date: Optional[datetime] = None
    surname: str = ""
    first_names: str = ""
    birth_date: Optional[datetime] = None
    preferred_language: str = ""


@dataclass
class VehicleRecord:
    timestamp_begin: Optional[datetime] = None
    timestamp_end: Optional[datetime] = None
    vrn: str = ""                  # Vehicle Registration Number (targa)
    registering_nation: str = ""
    odometer_begin: int = 0
    odometer_end: int = 0
    distance_km: int = 0


@dataclass
class ActivityRecord:
    date: Optional[datetime] = None
    activity: str = ""
    duration_minutes: int = 0
    slot: int = 0  # 0=driver, 1=co-driver


@dataclass
class DailyActivity:
    date: Optional[datetime] = None
    total_distance_km: int = 0
    activities: list = field(default_factory=list)
    driving_minutes: int = 0
    work_minutes: int = 0
    rest_minutes: int = 0
    availability_minutes: int = 0


# ── TLV Parser Core ─────────────────────────────────────────────────────────

class TLVParser:
    """
    Parser TLV per file .DDD di carte conducente.
    
    Legge sequenzialmente il file estraendo blocchi con struttura:
        tag (2 byte BE) + length (2 byte BE) + value (length byte)
    
    Per G2, gestisce anche firme (tag tipo 0x76xx) e blocchi annidati.
    """

    def __init__(self, data: bytes):
        self.data = data
        self.blocks: list[TLVBlock] = []
        self.pos = 0

    def parse_all(self) -> list[TLVBlock]:
        """Scansiona tutto il file estraendo blocchi TLV."""
        self.pos = 0
        self.blocks = []
        attempts = 0
        max_attempts = len(self.data)  # safety

        while self.pos < len(self.data) - 3 and attempts < max_attempts:
            attempts += 1
            block = self._read_block()
            if block is None:
                # Se non riconosciamo il tag, avanziamo di 1 byte
                self.pos += 1
                continue
            self.blocks.append(block)

        logger.info(f"Estratti {len(self.blocks)} blocchi TLV")
        return self.blocks

    def _read_block(self) -> Optional[TLVBlock]:
        """Legge un singolo blocco TLV dalla posizione corrente."""
        if self.pos + 4 > len(self.data):
            return None

        tag = struct.unpack(">H", self.data[self.pos:self.pos + 2])[0]

        # Verifica se è un tag conosciuto
        if tag not in DRIVER_CARD_TAGS:
            return None

        length = struct.unpack(">H", self.data[self.pos + 2:self.pos + 4])[0]

        # Sanity check sulla lunghezza
        if length > len(self.data) - (self.pos + 4) or length > 0xFFFF:
            return None
        if length == 0:
            # Blocco vuoto ma valido
            block = TLVBlock(
                tag=tag,
                tag_name=DRIVER_CARD_TAGS[tag],
                offset=self.pos,
                length=0,
                value=b''
            )
            self.pos += 4
            return block

        value = self.data[self.pos + 4:self.pos + 4 + length]
        block = TLVBlock(
            tag=tag,
            tag_name=DRIVER_CARD_TAGS[tag],
            offset=self.pos,
            length=length,
            value=value
        )
        self.pos += 4 + length

        # G2: se dopo il value c'è una firma (0x76), skippiamola
        if self.pos + 4 <= len(self.data):
            next_tag = struct.unpack(">H", self.data[self.pos:self.pos + 2])[0]
            if next_tag == 0x7600 or (next_tag >> 8) == 0x76:
                sig_len = struct.unpack(">H", self.data[self.pos + 2:self.pos + 4])[0]
                if sig_len <= len(self.data) - (self.pos + 4):
                    logger.debug(f"Skipping G2 signature block at {self.pos}, len={sig_len}")
                    self.pos += 4 + sig_len

        return block

    def get_blocks_by_tag(self, tag: int) -> list[TLVBlock]:
        return [b for b in self.blocks if b.tag == tag]

    def get_block(self, tag: int) -> Optional[TLVBlock]:
        blocks = self.get_blocks_by_tag(tag)
        return blocks[0] if blocks else None


# ── Data Decoders ────────────────────────────────────────────────────────────

def _ts_to_dt(data: bytes, offset: int = 0) -> Optional[datetime]:
    """Converte 4 byte Unix timestamp (BE) in datetime UTC."""
    if len(data) < offset + 4:
        return None
    ts = struct.unpack(">I", data[offset:offset + 4])[0]
    if ts == 0 or ts == 0xFFFFFFFF:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OSError, ValueError):
        return None


def _decode_string(data: bytes) -> str:
    """Decodifica stringa da dati binari, rimuovendo null e padding."""
    # I file DDD usano latin-1/ISO 8859-1 per le stringhe
    try:
        text = data.decode('latin-1')
    except Exception:
        text = data.decode('ascii', errors='ignore')
    return text.replace('\x00', '').strip()


def _decode_bcdhex_date(data: bytes) -> Optional[datetime]:
    """Decodifica data BCD (4 byte: YYYY MM DD) usata per date di nascita etc."""
    if len(data) < 4:
        return None
    try:
        year_hi = data[0]
        year_lo = data[1]
        month = data[2]
        day = data[3]
        year = year_hi * 100 + year_lo
        if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
            return datetime(year, month, day, tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def decode_identification(block: TLVBlock) -> DriverIdentification:
    """
    Decodifica EF_Identification (0x0502) o la variante G2 (0x0201).
    
    Struttura G1 (EF_Identification):
      cardIssuingMemberState(1) + cardNumber(16) + cardIssuingAuthorityName(36)
      + cardIssueDate(4) + cardValidityBegin(4) + cardExpiryDate(4)
      + holderSurname(36) + holderFirstNames(36) + cardHolderBirthDate(4)
      + cardHolderPreferredLanguage(2)
    """
    d = block.value
    info = DriverIdentification()

    if len(d) < 143:
        # File troppo corto, tentiamo estrazione parziale
        logger.warning(f"Identification block too short: {len(d)} bytes")
        # Tentativo fallback: cerchiamo il card number come prima stringa
        text = _decode_string(d)
        if text:
            info.card_number = text[:16].strip()
        return info

    pos = 0
    info.card_issuing_member_state = _decode_string(d[pos:pos + 1])
    pos += 1

    info.card_number = _decode_string(d[pos:pos + 16])
    pos += 16

    info.card_issuing_authority = _decode_string(d[pos:pos + 36])
    pos += 36

    info.card_issue_date = _ts_to_dt(d, pos)
    pos += 4

    info.card_validity_begin = _ts_to_dt(d, pos)
    pos += 4

    info.card_expiry_date = _ts_to_dt(d, pos)
    pos += 4

    # Nomi: 36 byte ciascuno
    info.surname = _decode_string(d[pos:pos + 36])
    pos += 36

    info.first_names = _decode_string(d[pos:pos + 36])
    pos += 36

    info.birth_date = _decode_bcdhex_date(d[pos:pos + 4])
    pos += 4

    info.preferred_language = _decode_string(d[pos:pos + 2])

    return info


def decode_vehicles_used(block: TLVBlock) -> list[VehicleRecord]:
    """
    Decodifica EF_Vehicles_Used (0x0507 / 0x0207).
    
    Struttura record singolo (31 byte G1):
      odometerBegin(3) + odometerEnd(3) + 
      firstUse_timestamp(4) + lastUse_timestamp(4) +
      vehicleRegistrationNation(1) + vehicleRegistrationNumber(14) +
      vuDataBlockCounter(2)
    
    Record alternativo (più comune):
      timestampBegin(4) + timestampEnd(4) + vrn_nation(1) + vrn(14) +
      vuOdometerBegin(3) + vuOdometerEnd(3)
    """
    data = block.value
    records = []

    if len(data) < 2:
        return records

    # Il primo campo è spesso vehiclePointerNewestRecord (2 byte)
    # poi i record veri e propri
    # Proviamo diverse strutture

    # Struttura tipica: pointer(2) + N * record(29 byte)
    record_size_29 = 29
    record_size_31 = 31

    for record_size in [record_size_29, record_size_31]:
        offset = 2  # skip pointer
        temp_records = []
        while offset + record_size <= len(data):
            rec = _try_decode_vehicle_record(data, offset, record_size)
            if rec is not None:
                temp_records.append(rec)
            offset += record_size

        if temp_records:
            records = temp_records
            break

    # Fallback: prova senza pointer
    if not records:
        for record_size in [record_size_29, record_size_31]:
            offset = 0
            temp_records = []
            while offset + record_size <= len(data):
                rec = _try_decode_vehicle_record(data, offset, record_size)
                if rec is not None:
                    temp_records.append(rec)
                offset += record_size
            if temp_records:
                records = temp_records
                break

    return records


def _try_decode_vehicle_record(data: bytes, offset: int, size: int) -> Optional[VehicleRecord]:
    """Tenta di decodificare un singolo record veicolo."""
    d = data[offset:offset + size]

    # Formato comune: ts_begin(4) + ts_end(4) + nation(1) + vrn(14) + odo_begin(3) + odo_end(3) = 29
    if size == 29 and len(d) >= 29:
        ts_begin = _ts_to_dt(d, 0)
        ts_end = _ts_to_dt(d, 4)

        if ts_begin is None and ts_end is None:
            return None

        nation = _decode_string(d[8:9])
        vrn = _decode_string(d[9:23])
        odo_begin = int.from_bytes(d[23:26], 'big')
        odo_end = int.from_bytes(d[26:29], 'big')

        # Validazione
        if not vrn or not any(c.isalnum() for c in vrn):
            return None
        if odo_end < odo_begin or odo_begin > 9_999_999:
            return None

        rec = VehicleRecord(
            timestamp_begin=ts_begin,
            timestamp_end=ts_end,
            vrn=vrn,
            registering_nation=nation,
            odometer_begin=odo_begin,
            odometer_end=odo_end,
            distance_km=odo_end - odo_begin
        )
        return rec

    # Formato alternativo: odo_begin(3) + odo_end(3) + ts_begin(4) + ts_end(4) + nation(1) + vrn(14) + counter(2) = 31
    if size == 31 and len(d) >= 31:
        odo_begin = int.from_bytes(d[0:3], 'big')
        odo_end = int.from_bytes(d[3:6], 'big')
        ts_begin = _ts_to_dt(d, 6)
        ts_end = _ts_to_dt(d, 10)

        if ts_begin is None and ts_end is None:
            return None

        nation = _decode_string(d[14:15])
        vrn = _decode_string(d[15:29])

        if not vrn or not any(c.isalnum() for c in vrn):
            return None
        if odo_end < odo_begin or odo_begin > 9_999_999:
            return None

        rec = VehicleRecord(
            timestamp_begin=ts_begin,
            timestamp_end=ts_end,
            vrn=vrn,
            registering_nation=nation,
            odometer_begin=odo_begin,
            odometer_end=odo_end,
            distance_km=odo_end - odo_begin
        )
        return rec

    return None


def decode_activity_data(block: TLVBlock) -> list[DailyActivity]:
    """
    Decodifica EF_Driver_Activity_Data (0x0506 / 0x0206).
    
    Struttura:
      pointerOldestDayRecord(2) + pointerNewestDayRecord(2) + activityRecords(...)
    
    Ogni DayRecord:
      activityRecordDate(4) + dailyPresenceCounter(2) + activityDayDistance(2) +
      N * activityChangeInfo(2)
    
    activityChangeInfo (2 byte, big-endian):
      bit 15: slot (0=driver, 1=co-driver)
      bit 14: crew status (0=single, 1=crew)
      bit 13: card status (0=inserted, 1=not inserted)  
      bits 12-10: activity (0=break, 1=avail, 2=work, 3=driving)
      bits 9-0: time in minutes from 00:00
    
    Fine record: si riconosce dal prossimo timestamp valido o fine dati.
    """
    data = block.value
    days = []

    if len(data) < 4:
        return days

    # Leggi i pointer (offset relativi nell'area dati)
    ptr_oldest = struct.unpack(">H", data[0:2])[0]
    ptr_newest = struct.unpack(">H", data[2:4])[0]

    logger.debug(f"Activity data: {len(data)} bytes, ptr_oldest={ptr_oldest}, ptr_newest={ptr_newest}")

    # I record giornalieri iniziano all'offset 4 (dopo i 2 pointer)
    # Scansioniamo cercando timestamp validi come inizio record
    pos = 4
    while pos + 8 <= len(data):
        # Leggi potenziale timestamp data
        ts = struct.unpack(">I", data[pos:pos + 4])[0]
        dt = None
        try:
            if 946684800 < ts < 2524608000:  # 2000-01-01 to 2050-01-01
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OSError, ValueError):
            pass

        if dt is None:
            pos += 1
            continue

        # Potenziale inizio di un day record
        if pos + 8 > len(data):
            break

        daily_presence = struct.unpack(">H", data[pos + 4:pos + 6])[0]
        daily_distance = struct.unpack(">H", data[pos + 6:pos + 8])[0]

        # Sanity: distanza giornaliera < 2000 km
        if daily_distance > 2000:
            pos += 1
            continue

        # Leggi le activity change entries (2 byte ciascuna)
        act_pos = pos + 8
        activities = []
        prev_minutes = -1

        while act_pos + 2 <= len(data):
            entry = struct.unpack(">H", data[act_pos:act_pos + 2])[0]

            if entry == 0x0000 or entry == 0xFFFF:
                act_pos += 2
                break

            slot = (entry >> 15) & 1
            # crew = (entry >> 14) & 1
            # card = (entry >> 13) & 1
            activity_code = (entry >> 10) & 0x07
            minutes = entry & 0x3FF

            # Validazione: minuti < 1440, codice attività < 4
            if minutes >= 1440 or activity_code > 3:
                break

            # I minuti devono essere non-decrescenti
            if minutes < prev_minutes:
                break

            activities.append(ActivityRecord(
                date=dt,
                activity=ACTIVITY_CODES.get(activity_code, f"UNKNOWN({activity_code})"),
                duration_minutes=0,  # calcoleremo dopo
                slot=slot
            ))
            prev_minutes = minutes
            act_pos += 2

        # Calcola durate tra cambi attività
        for i in range(len(activities)):
            if i + 1 < len(activities):
                entry_curr = struct.unpack(">H", data[pos + 8 + i * 2:pos + 8 + i * 2 + 2])[0]
                entry_next = struct.unpack(">H", data[pos + 8 + (i + 1) * 2:pos + 8 + (i + 1) * 2 + 2])[0]
                min_curr = entry_curr & 0x3FF
                min_next = entry_next & 0x3FF
                activities[i].duration_minutes = min_next - min_curr
            else:
                # Ultimo record: fino a fine giornata o stima
                entry_curr = struct.unpack(">H", data[pos + 8 + i * 2:pos + 8 + i * 2 + 2])[0]
                min_curr = entry_curr & 0x3FF
                activities[i].duration_minutes = max(0, 1440 - min_curr)

        if activities:
            day = DailyActivity(
                date=dt,
                total_distance_km=daily_distance,
                activities=activities,
                driving_minutes=sum(a.duration_minutes for a in activities if a.activity == "GUIDA"),
                work_minutes=sum(a.duration_minutes for a in activities if a.activity == "LAVORO"),
                rest_minutes=sum(a.duration_minutes for a in activities if a.activity == "RIPOSO"),
                availability_minutes=sum(a.duration_minutes for a in activities if a.activity == "DISPONIBILITÀ"),
            )
            days.append(day)

        pos = act_pos  # Avanza al prossimo record

    # Ordina per data
    days.sort(key=lambda d: d.date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return days


# ── Main Parser (public API) ────────────────────────────────────────────────

class DDDParser:
    """
    Parser completo per file .DDD di carte conducente.
    
    Uso:
        parser = DDDParser("file.ddd")
        result = parser.parse()
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.raw_data: Optional[bytes] = None
        self.tlv: Optional[TLVParser] = None
        self.generation = "Unknown"
        self.identification = DriverIdentification()
        self.vehicles: list[VehicleRecord] = []
        self.daily_activities: list[DailyActivity] = []

    def parse(self) -> Optional[dict]:
        """Esegue il parsing completo e restituisce un dizionario strutturato."""
        if not self._load_file():
            return None

        self._detect_generation()
        self._parse_tlv()
        self._decode_all()

        return self._build_result()

    def _load_file(self) -> bool:
        if not os.path.exists(self.file_path):
            logger.error(f"File non trovato: {self.file_path}")
            return False
        try:
            with open(self.file_path, 'rb') as f:
                self.raw_data = f.read()
            if len(self.raw_data) < 10:
                logger.error("File troppo piccolo")
                return False
            logger.info(f"Caricato {self.file_path}: {len(self.raw_data)} byte")
            return True
        except IOError as e:
            logger.error(f"Errore lettura file: {e}")
            return False

    def _detect_generation(self):
        """Rileva G1 vs G2 dal primo tag o da firme caratteristiche."""
        if self.raw_data[:2] in (b'\x00\x02', b'\x00\x05', b'\x00\x06'):
            self.generation = "G1 (Digital Tachograph)"
        elif self.raw_data[:1] == b'\x76' or any(
            struct.unpack(">H", self.raw_data[i:i+2])[0] in (0x0201, 0x0202, 0x0206, 0x0207)
            for i in range(0, min(20, len(self.raw_data) - 1), 2)
        ):
            self.generation = "G2 (Smart Tachograph)"
        else:
            # Fallback: scansione per tag noti
            self.generation = "G1 (Digital Tachograph)"

    def _parse_tlv(self):
        """Esegue parsing TLV strutturale."""
        self.tlv = TLVParser(self.raw_data)
        self.tlv.parse_all()
        logger.info(f"Blocchi trovati: {[str(b) for b in self.tlv.blocks]}")

    def _decode_all(self):
        """Decodifica tutti i blocchi riconosciuti."""
        # ── Identification ──
        id_block = self.tlv.get_block(0x0502) or self.tlv.get_block(0x0201)
        if id_block:
            self.identification = decode_identification(id_block)

        # Se non troviamo il numero carta dall'identification, fallback ICC
        if not self.identification.card_number:
            icc = self.tlv.get_block(0x0002)
            if icc and len(icc.value) >= 25:
                # ICC contiene clock_stop(4), card_extended_serial(8), ...
                # card number è tipicamente in EF_Identification
                pass

        # ── Vehicles Used ──
        veh_block = self.tlv.get_block(0x0507) or self.tlv.get_block(0x0207)
        if veh_block:
            self.vehicles = decode_vehicles_used(veh_block)

        # ── Activity Data ──
        act_block = self.tlv.get_block(0x0506) or self.tlv.get_block(0x0206)
        if act_block:
            self.daily_activities = decode_activity_data(act_block)

    def _build_result(self) -> dict:
        """Costruisce il dizionario risultato."""
        ident = self.identification

        # Ricava la targa più recente dai veicoli
        plate = ""
        vin = ""
        if self.vehicles:
            # Ordina per timestamp più recente
            sorted_v = sorted(
                self.vehicles,
                key=lambda v: v.timestamp_end or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True
            )
            plate = sorted_v[0].vrn if sorted_v else ""

        # Formatta i viaggi (vehicle records) per retrocompatibilità con la GUI
        trips = []
        for v in self.vehicles:
            if v.timestamp_begin and v.timestamp_end:
                trips.append({
                    "data": v.timestamp_begin.strftime('%d/%m/%Y'),
                    "inizio": v.timestamp_begin.strftime('%H:%M'),
                    "fine": v.timestamp_end.strftime('%H:%M'),
                    "targa": v.vrn,
                    "km_inizio": v.odometer_begin,
                    "km_fine": v.odometer_end,
                    "distanza": v.distance_km,
                })

        trips.sort(key=lambda x: (x["data"], x["inizio"]), reverse=True)

        # Formatta le attività giornaliere
        daily_summary = []
        for day in self.daily_activities:
            daily_summary.append({
                "data": day.date.strftime('%d/%m/%Y') if day.date else "N/D",
                "km_totali": day.total_distance_km,
                "guida_min": day.driving_minutes,
                "lavoro_min": day.work_minutes,
                "riposo_min": day.rest_minutes,
                "disponibilità_min": day.availability_minutes,
                "guida_ore": f"{day.driving_minutes // 60}h{day.driving_minutes % 60:02d}m",
                "attività": [
                    {"tipo": a.activity, "durata_min": a.duration_minutes}
                    for a in day.activities
                ]
            })

        return {
            "metadata": {
                "filename": os.path.basename(self.file_path),
                "filesize": len(self.raw_data),
                "generation": self.generation,
                "parsed_at": datetime.now().isoformat(),
                "tlv_blocks_found": len(self.tlv.blocks),
                "tlv_tags": [f"0x{b.tag:04X} ({b.tag_name})" for b in self.tlv.blocks],
            },
            "driver": {
                "card_number": ident.card_number or "Non rilevato",
                "surname": ident.surname or "",
                "first_names": ident.first_names or "",
                "birth_date": ident.birth_date.strftime('%d/%m/%Y') if ident.birth_date else "",
                "card_issuing_authority": ident.card_issuing_authority or "",
                "card_issue_date": ident.card_issue_date.strftime('%d/%m/%Y') if ident.card_issue_date else "",
                "card_expiry_date": ident.card_expiry_date.strftime('%d/%m/%Y') if ident.card_expiry_date else "",
                "preferred_language": ident.preferred_language or "",
            },
            "vehicle": {
                "plate": plate or "Non rilevata",
                "vin": vin or "Non rilevato",
            },
            "trips": trips,
            "daily_activities": daily_summary,
        }

    def get_tlv_blocks(self) -> list[TLVBlock]:
        """Accesso diretto ai blocchi TLV (per debug/analisi)."""
        return self.tlv.blocks if self.tlv else []


# ── Alias per retrocompatibilità ─────────────────────────────────────────────
TachoParser = DDDParser


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        parser = DDDParser(sys.argv[1])
        result = parser.parse()
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("Errore nel parsing del file.", file=sys.stderr)
            sys.exit(1)
    else:
        print("Uso: python ddd_parser.py <file.ddd>", file=sys.stderr)
