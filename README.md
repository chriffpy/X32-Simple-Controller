# X32 Simple Controller

Eine benutzerfreundliche Weboberfläche zur Steuerung des Behringer X32 Digital-Mixers.

**Autor:** Christopher Gertig  
**Erstellt:** Dezember 2024  
**Lizenz:** MIT

![IMG_0007](https://github.com/user-attachments/assets/c3ed7409-4a62-4ca0-af90-a0804512d937)

## Features

- Intuitive Benutzeroberfläche für häufig genutzte Mixer-Funktionen
- 6 konfigurierbare Kanal-Fader mit Mute-Buttons
- Master-Fader mit Mute-Funktion
- Echtzeit Audio-Level-Meter für Main L/R
- Gong-Funktion für Ankündigungen
- Echtzeit-Steuerung über WebSocket-Verbindung
- Responsive Design (optimiert für Desktop und Mobile)
- Progressive Web App (PWA) Unterstützung
- Automatische Wiederverbindung bei Verbindungsabbruch

## Installation

1. Python-Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

2. Konfiguration anpassen:
   - Öffnen Sie `config.py`
   - Passen Sie die IP-Adresse des X32 an (`X32_IP`)
   - Optional: Passen Sie die Ports und das Kanal-Mapping an

## Starten

```bash
python main.py
```

Der Controller ist dann unter `http://localhost:8000` erreichbar.

## Kanal-Konfiguration

Die Standard-Kanalkonfiguration ist wie folgt:
- Kanal 1: Headset 1 (X32 Channel 1)
- Kanal 2: Headset 2 (X32 Channel 2)
- Kanal 3: Hand 1 (X32 Channel 3)
- Kanal 4: Hand 2 (X32 Channel 4)
- Kanal 5: HDMI (X32 Channel 11)
- Kanal 6: Regie (X32 Channel 13)

Die Kanal-Zuordnung kann in der `config.py` angepasst werden.

## Technische Details

- Backend: Python mit FastAPI und python-osc
- Frontend: Vanilla JavaScript mit WebSocket-Kommunikation
- OSC-Kommunikation mit dem X32 über UDP
- Automatisches Reconnect mit exponentieller Backoff-Strategie
- Meter-Anzeige mit Farbkodierung:
  - Grün: unter -12 dB
  - Gelb: -12 dB bis -6 dB
  - Rot: über -6 dB

## Datenschutz & Sicherheit

Diese Software:
- Speichert keine personenbezogenen Daten
- Verwendet keine Cookies oder lokale Speicherung
- Sendet keine Daten an externe Server
- Kommuniziert ausschließlich im lokalen Netzwerk
- Zeichnet keine Audio-Daten auf

⚠️ **Sicherheitshinweis:** Da das X32 keine eigene Authentifizierung für OSC-Befehle bietet, sollte diese Software nur in vertrauenswürdigen, gesicherten Netzwerken betrieben werden.

## Sicherheitshinweise

- Der Controller sollte nur in vertrauenswürdigen Netzwerken betrieben werden
- Der X32 bietet keine Authentifizierung für OSC-Befehle
- Stellen Sie sicher, dass der Zugriff auf den Controller entsprechend eingeschränkt ist

## Fehlersuche

1. Keine Verbindung zum X32:
   - Überprüfen Sie die IP-Adresse in `config.py`
   - Stellen Sie sicher, dass der X32 eingeschaltet und im Netzwerk erreichbar ist
   - Prüfen Sie, ob Port 10023 (OSC) nicht blockiert ist

2. Keine Meter-Anzeige:
   - Überprüfen Sie, ob der X32 Meter-Daten sendet
   - Prüfen Sie die WebSocket-Verbindung in den Browser-Entwicklertools

3. Verbindungsabbrüche:
   - Der Controller versucht automatisch, die Verbindung wiederherzustellen
   - Überprüfen Sie die Netzwerkstabilität
   - Prüfen Sie die Firewall-Einstellungen

## Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe die [LICENSE](LICENSE) Datei für Details.

Die MIT-Lizenz ist eine permissive Lizenz, die nur minimale Einschränkungen für die Wiederverwendung auferlegt. Die Hauptanforderung ist, dass der Copyright-Hinweis und die Lizenz in allen Kopien oder wesentlichen Teilen der Software enthalten sein müssen.
