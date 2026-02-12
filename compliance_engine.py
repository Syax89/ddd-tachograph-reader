from datetime import datetime, timedelta

class ComplianceEngine:
    """
    Engine for calculating compliance with EU Regulation 561/2006.
    Analyzes driver activities to detect infractions.
    """

    def __init__(self):
        self.infractions = []

    def analyze(self, activities):
        """
        Analyzes the list of activities and returns a list of infractions.
        activities: list of daily activity records from TachoParser.
        """
        if not activities:
            return []

        self.infractions = []
        
        # Sort activities by date to handle weekly calculations if needed
        # activities format: {"data": "DD/MM/YYYY", "km": dist, "eventi": [{"tipo": "...", "ora": "HH:MM", "slot": "..."}]}
        sorted_days = sorted(activities, key=lambda x: datetime.strptime(x["data"], "%d/%m/%Y"))

        weekly_guida_10h_count = {} # ISO week -> count of 10h days

        for day in sorted_days:
            self._analyze_daily(day, weekly_guida_10h_count)

        return self.infractions

    def _analyze_daily(self, day, weekly_guida_10h_count):
        date_str = day["data"]
        events = day["eventi"]
        if not events:
            return

        # Convert events to absolute minutes from midnight for easier calculation
        # and calculate durations between events.
        timeline = []
        for ev in events:
            try:
                time_parts = ev["ora"].split(":")
                if len(time_parts) != 2: continue
                h, m = map(int, time_parts)
                timeline.append({
                    "start": max(0, min(1440, h * 60 + m)),
                    "tipo": ev["tipo"]
                })
            except (ValueError, TypeError):
                continue
        
        # Sort timeline by start time to handle out-of-order events
        timeline.sort(key=lambda x: x["start"])
        
        # Add end of day (24:00) to close the last activity
        if timeline:
            timeline.append({"start": 24 * 60, "tipo": "END"})

        durations = {"GUIDA": 0, "RIPOSO": 0, "LAVORO": 0, "DISPONIBILITÀ": 0}
        
        current_guida_session = 0
        consecutive_guida = 0
        total_guida = 0
        max_consecutive_guida = 0
        
        # 1. Daily Driving Time & Continuous Driving
        for i in range(len(timeline) - 1):
            start = timeline[i]["start"]
            end = timeline[i+1]["start"]
            duration = end - start
            tipo = timeline[i]["tipo"]
            
            if tipo == "GUIDA":
                total_guida += duration
                consecutive_guida += duration
                # Check for 4.5h rule (270 minutes)
                if consecutive_guida > 270:
                    # Potential infraction, but we must check if a break occurred before
                    # This logic is simplified: real 561/2006 requires 45min break (or 15+30)
                    pass 
            elif tipo == "RIPOSO" or tipo == "DISPONIBILITÀ":
                # Check if it's a valid break for the 4.5h rule
                if duration >= 45:
                    consecutive_guida = 0
                # Simplified check for split break (15 + 30) - omitted for brevity in this MVP
                elif duration >= 15:
                    # In a real implementation, we'd track if this is the first part of a split
                    pass
            else: # LAVORO
                pass

        # Check Daily Driving Limit (9h = 540 min, 10h = 600 min)
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        week_num = dt.isocalendar()[1]
        year = dt.year
        week_key = f"{year}-W{week_num}"

        if total_guida > 600:
            self.infractions.append({
                "data": date_str,
                "tipo": "ECCESSO_GUIDA_GIORNALIERA",
                "descrizione": f"Guida giornaliera di {total_guida} min supera il limite massimo di 10h."
            })
        elif total_guida > 540:
            count = weekly_guida_10h_count.get(week_key, 0)
            if count >= 2:
                self.infractions.append({
                    "data": date_str,
                    "tipo": "ECCESSO_GUIDA_GIORNALIERA",
                    "descrizione": f"Guida giornaliera di {total_guida} min supera le 9h per la terza volta nella settimana."
                })
            else:
                weekly_guida_10h_count[week_key] = count + 1

        # 2. Breaks (45 min every 4.5h)
        # Re-evaluating consecutive driving more strictly
        temp_consecutive = 0
        for i in range(len(timeline) - 1):
            start = timeline[i]["start"]
            end = timeline[i+1]["start"]
            duration = end - start
            tipo = timeline[i]["tipo"]
            
            if tipo == "GUIDA":
                temp_consecutive += duration
                if temp_consecutive > 270:
                    self.infractions.append({
                        "data": date_str,
                        "tipo": "PAUSA_INSUFFICIENTE",
                        "descrizione": f"Guida ininterrotta superiore a 4.5h ({temp_consecutive} min) senza pausa di 45 min."
                    })
                    temp_consecutive = 0 # Reset after reporting to avoid duplicate for same stretch
            elif tipo == "RIPOSO" or tipo == "DISPONIBILITÀ":
                if duration >= 45:
                    temp_consecutive = 0
            # Split break 15+30 is complex to implement without state machine, keeping it simple for now.

        # 3. Daily Rest (11h = 660 min, reduced 9h = 540 min)
        # Note: Rest is usually measured in a 24h period starting from the end of previous rest.
        # For simplicity in this parser, we look at the longest rest period within the calendar day.
        max_rest = 0
        for i in range(len(timeline) - 1):
            if timeline[i]["tipo"] == "RIPOSO":
                duration = timeline[i+1]["start"] - timeline[i]["start"]
                if duration > max_rest:
                    max_rest = duration
        
        if max_rest < 540: # Less than 9h
            self.infractions.append({
                "data": date_str,
                "tipo": "RIPOSO_GIORNALIERO_INSUFFICIENTE",
                "descrizione": f"Riposo giornaliero massimo di {max_rest} min è inferiore al minimo di 9h."
            })
        elif max_rest < 660: # Between 9h and 11h
            # Reduced rest is allowed 3 times between two weekly rests.
            # Tracking this across days is complex; we'll flag it as "Reduced" for the user to see.
            pass

    def get_report(self):
        return self.infractions
