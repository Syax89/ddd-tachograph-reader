from datetime import datetime, timedelta

class ComplianceEngine:
    """
    Senior Regulatory Compliance Engine for EU Regulation 561/2006.
    Implements complex logic for split breaks, 24-hour shift cycles, and infraction severity.
    """

    # Severity Constants
    MSI = "MSI"  # Most Serious Infringement
    SI  = "SI"   # Serious Infringement
    MI  = "MI"   # Minor Infringement

    def __init__(self):
        self.infractions = []

    def analyze(self, activities):
        """
        Analyzes activities across multiple days.
        Activities format: list of {"data": "DD/MM/YYYY", "eventi": [{"tipo": "...", "ora": "HH:MM", "durata": min}]}
        Note: The input format is slightly adjusted to ensure durations are handled correctly.
        """
        if not activities:
            return []

        self.infractions = []
        
        # 1. Build a continuous timeline of events
        timeline = self._build_timeline(activities)
        if not timeline:
            return []

        # 2. Analyze Continuous Driving and Split Breaks
        self._check_driving_and_breaks(timeline)

        # 3. Analyze Daily Rest (24h Shift Logic)
        self._check_daily_rest_cycles(timeline)

        return self.infractions

    def _build_timeline(self, activities):
        """Converts day-based activity objects into a flat list of chronological events."""
        full_timeline = []
        sorted_days = sorted(activities, key=lambda x: datetime.strptime(x["data"], "%d/%m/%Y"))

        for day in sorted_days:
            date_base = datetime.strptime(day["data"], "%d/%m/%Y")
            events = day.get("eventi", [])
            for ev in events:
                h, m = map(int, ev["ora"].split(":"))
                start_dt = date_base + timedelta(hours=h, minutes=m)
                
                # In the original data, we might have duration or just start times.
                # Assuming 'durata' is available from the parser or inferred.
                # If not, we'd need to calculate it from the next event.
                # For this logic, we assume events have a duration.
                durata = ev.get("durata", 0)
                if durata <= 0: continue
                
                full_timeline.append({
                    "start": start_dt,
                    "end": start_dt + timedelta(minutes=durata),
                    "tipo": ev["tipo"],
                    "durata": durata
                })
        
        # Secondary safety sort
        full_timeline.sort(key=lambda x: x["start"])
        return full_timeline

    def _check_driving_and_breaks(self, timeline):
        """
        Objective 2: Implementa la logica della 'Pausa Frazionata'.
        Rule: 4.5h driving -> 45m break. 
        Split: 15m (min) followed by 30m (min).
        """
        driving_accumulator = 0
        has_15m_part = False

        for ev in timeline:
            tipo = ev["tipo"]
            durata = ev["durata"]

            if tipo == "GUIDA":
                driving_accumulator += durata
                if driving_accumulator > 270:
                    # We have an infraction
                    excess = driving_accumulator - 270
                    severity = self._get_driving_severity(excess)
                    self.infractions.append({
                        "data": ev["start"].strftime("%d/%m/%Y"),
                        "tipo": "ECCESSO_GUIDA_CONTINUA",
                        "severita": severity,
                        "descrizione": f"Guida continua di {driving_accumulator} min supera il limite di 4.5h."
                    })
                    # Reset accumulator after infraction to catch the next stretch
                    driving_accumulator = 0
                    has_15m_part = False

            elif tipo in ["RIPOSO", "DISPONIBILITÀ"]:
                # Logic for Split Break
                if durata >= 45:
                    driving_accumulator = 0
                    has_15m_part = False
                elif not has_15m_part and durata >= 15:
                    has_15m_part = True
                    # Driving accumulator is NOT reset yet
                elif has_15m_part and durata >= 30:
                    driving_accumulator = 0
                    has_15m_part = False
                # If it's a small break < 15, it does nothing to the accumulator

            else: # LAVORO
                # Work doesn't reset driving, but it counts towards the shift (handled in daily rest)
                pass

    def _check_daily_rest_cycles(self, timeline):
        """
        Objective 3: Implementa il calcolo del 'Turno di 24 ore'.
        Rule: Within 24h from the start of activities, a rest of 11h (or 9h reduced) must be completed.
        """
        if not timeline: return

        # Identify the start of the first shift
        # A shift starts after a significant rest (> 9h)
        idx = 0
        n = len(timeline)
        
        while idx < n:
            # Start of a shift is the first non-rest activity
            shift_start_ev = None
            for i in range(idx, n):
                if timeline[i]["tipo"] != "RIPOSO":
                    shift_start_ev = timeline[i]
                    idx = i
                    break
            
            if not shift_start_ev: break
            
            shift_limit = shift_start_ev["start"] + timedelta(hours=24)
            
            # Look for the longest rest period that FINISHES within this 24h window
            # and starts after the activities began.
            max_rest_in_window = 0
            found_rest_end = shift_start_ev["start"]
            
            # Track if we found a valid daily rest
            current_idx = idx
            while current_idx < n and timeline[current_idx]["start"] < shift_limit:
                ev = timeline[current_idx]
                if ev["tipo"] == "RIPOSO":
                    # Rest must be finished within the 24h window to count
                    # If it overflows, only the part within 24h counts? 
                    # Actually, the requirement is "completed within 24h".
                    if ev["end"] <= shift_limit:
                        max_rest_in_window = max(max_rest_in_window, ev["durata"])
                    else:
                        # Part of rest within window
                        minutes_within = (shift_limit - ev["start"]).total_seconds() / 60
                        if minutes_within > 0:
                            max_rest_in_window = max(max_rest_in_window, minutes_within)
                
                found_rest_end = ev["end"]
                current_idx += 1

            # Determine infraction
            if max_rest_in_window < 540: # Less than 9h (minimum reduced rest)
                shortfall = 540 - max_rest_in_window
                severity = self._get_rest_severity(shortfall)
                self.infractions.append({
                    "data": shift_start_ev["start"].strftime("%d/%m/%Y"),
                    "tipo": "RIPOSO_GIORNALIERO_INSUFFICIENTE",
                    "severita": severity,
                    "descrizione": f"Entro il turno di 24h (inizio {shift_start_ev['start'].strftime('%H:%M')}), il riposo massimo completato è di {int(max_rest_in_window)} min (minimo 9h)."
                })
            
            # Advance to the next shift: find the next activity after a rest > 9h
            # This is a simplification: usually the next shift starts after the daily rest.
            found_next_shift = False
            for i in range(current_idx - 1, n):
                if timeline[i]["tipo"] == "RIPOSO" and timeline[i]["durata"] >= 540:
                    idx = i + 1
                    found_next_shift = True
                    break
            
            if not found_next_shift:
                break # No more shifts found

    def _get_driving_severity(self, excess_min):
        """Objective 4: Aggiungi la severità dell'infrazione."""
        if excess_min <= 30: return self.MI
        if excess_min <= 90: return self.SI
        return self.MSI

    def _get_rest_severity(self, shortfall_min):
        """Objective 4: Aggiungi la severità dell'infrazione."""
        if shortfall_min <= 60: return self.MI
        if shortfall_min <= 120: return self.SI
        return self.MSI

    def get_report(self):
        return self.infractions
