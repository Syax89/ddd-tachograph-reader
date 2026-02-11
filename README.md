# 🚛 DDD Tachograph Reader

Un analizzatore moderno e veloce per file `.ddd` (Tachigrafo Digitale), progettato per estrarre informazioni su veicoli, conducenti e cronologia dei viaggi.

## ✨ Caratteristiche
- **Analisi Multi-Generazione**: Supporta file G1 (Digital) e G2 (Smart Tachograph).
- **Estrazione Dati Mezzo**: Recupero automatico di VIN (Telaio) e Targa.
- **Cronologia Viaggi**: Tabella dettagliata con date, orari di inizio/fine e chilometraggi.
- **Interfaccia Moderna**: GUI in Dark Mode basata su CustomTkinter.
- **Portable**: Disponibile come file eseguibile (.exe) per Windows.

## 🚀 Utilizzo Rapido

### GUI (Consigliata)
Scarica l'ultimo eseguibile dalla sezione **Releases** o **Actions** di questo repository ed esegui `DDD-Reader.exe`.

### Riga di Comando
Se preferisci usare Python direttamente:
```bash
pip install -r requirements.txt
python main.py percorso/del/file.ddd
```

## 🛠️ Requisiti (per sviluppatori)
- Python 3.10+
- `customtkinter`
- `pyinstaller` (per compilare l'eseguibile)

## 🏗️ Build Personale
Per creare il tuo file eseguibile locale:
```bash
pyinstaller --noconfirm --onefile --windowed --name "DDD-Reader" --add-data "venv/Lib/site-packages/customtkinter;customtkinter" gui.py
```
*(Nota: il percorso di `customtkinter` potrebbe variare in base al tuo ambiente).*

## ⚖️ Licenza
Distribuito sotto licenza MIT. Vedere `LICENSE` per ulteriori informazioni.

---
*Sviluppato con ✨ da Aurora per Simone Rondina.*
