# X32 Simple Controller

Eine benutzerfreundliche Weboberfläche zur Steuerung des Behringer X32.

## Features

- 6 konfigurierbare Kanal-Fader
- Master-Fader
- Mute-Buttons für alle Kanäle
- Echtzeit-Steuerung über WebSocket
- Responsive Design (funktioniert auf Desktop und Mobile)

## Installation

1. Python-Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

2. Konfiguration anpassen:
   - Öffnen Sie `config.py`
   - Passen Sie die IP-Adresse des X32 an (`X32_IP`)

## Starten

```bash
python main.py
```

Der Controller ist dann unter `http://localhost:8000` erreichbar.

## Kanal-Konfiguration

Die Kanäle sind wie folgt konfiguriert:
- Kanal 1: Headset 1 (X32 Channel 1)
- Kanal 2: Headset 2 (X32 Channel 2)
- Kanal 3: Hand 1 (X32 Channel 3)
- Kanal 4: Hand 2 (X32 Channel 4)
- Kanal 5: HDMI (X32 Channel 11)
- Kanal 6: Regie (X32 Channel 13)

Die Kanal-Zuordnung kann in der `config.py` angepasst werden.
