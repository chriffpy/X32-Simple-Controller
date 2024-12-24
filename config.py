"""
X32 Simple Controller - Konfigurationsdatei
Autor: Christopher Gertig
Erstellt: Dezember 2024
"""

# Netzwerkkonfiguration für den X32 Digitalmixer
X32_IP = "192.168.217.20"  # IP-Adresse des X32 Mixers im Netzwerk
X32_PORT = 10023  # Standard OSC-Port für die X32-Kommunikation
LOCAL_PORT = 64431  # Lokaler Port für den OSC-Server

# Kanal-Mapping: Anzeigename -> Tatsächlicher X32-Kanal
# Dies ordnet die benutzerfreundlichen Namen den physischen Kanälen des Mixers zu
CHANNEL_MAPPING = {
    "Headset 1": 1,    # Erstes Headset-Mikrofon
    "Headset 2": 2,    # Zweites Headset-Mikrofon
    "Hand 1": 3,       # Erstes Handmikrofon
    "Hand 2": 4,       # Zweites Handmikrofon
    "HDMI": 11,        # HDMI-Audioeingang
    "Regie": 13        # Regiekanal für Kommunikation
}
