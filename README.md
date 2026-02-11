# DDD Tachograph Reader

Un semplice lettore di file DDD per tachigrafo digitale, basato sulla libreria `tachoparser`.

## Caratteristiche
- Supporta file DDD di 1ª e 2ª generazione.
- Parsing dei dati del veicolo e della carta conducente.
- Output in formato JSON per una facile integrazione.

## Installazione

Assicurati di avere Python 3 installato, quindi installa le dipendenze:

```bash
pip install -r requirements.txt
```

## Utilizzo

Per leggere un file DDD e visualizzare il risultato a schermo:

```bash
python main.py percorso/del/file.ddd
```

Per salvare il risultato in un file JSON:

```bash
python main.py percorso/del/file.ddd -o output.json
```

## Crediti
Questo progetto utilizza la libreria [tachoparser](https://github.com/traconiq/tachoparser) di traconiq.
