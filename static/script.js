/**
 * X32 Simple Controller
 * Autor: Christopher Gertig
 * Erstellt: Dezember 2024
 */

// WebSocket-Verbindungsvariablen
let ws = null;
let reconnectTimeout = null;
const RECONNECT_DELAY = 1000; // Initiale Wiederverbindungsverzögerung: 1 Sekunde
const MAX_RECONNECT_DELAY = 5000; // Maximale Verzögerung: 5 Sekunden
let currentReconnectDelay = RECONNECT_DELAY;

// Funktion zum Aufbau der WebSocket-Verbindung
function connectWebSocket() {
    if (ws !== null && ws.readyState !== WebSocket.CLOSED) {
        return;
    }
    
    clearTimeout(reconnectTimeout);
    
    // Wähle das korrekte WebSocket-Protokoll basierend auf der Seitenverbindung
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    
    // Event-Handler für erfolgreiche Verbindung
    ws.onopen = () => {
        console.log('Verbunden mit Server');
        currentReconnectDelay = RECONNECT_DELAY; // Setze Verzögerung zurück
        clearTimeout(reconnectTimeout);
        
        // Anfrage der initialen Werte vom Server
        ws.send(JSON.stringify({
            type: 'request_initial_values'
        }));
        
        initializeChannels();
        setupEventListeners();
    };
    
    // Event-Handler für Verbindungsabbruch
    ws.onclose = () => {
        console.log('Verbindung zum Server abgebrochen - Versuche, erneut zu verbinden...');
        clearTimeout(reconnectTimeout);
        
        // Exponentielles Backoff mit maximaler Verzögerung
        currentReconnectDelay = Math.min(currentReconnectDelay * 1.5, MAX_RECONNECT_DELAY);
        reconnectTimeout = setTimeout(connectWebSocket, currentReconnectDelay);
    };
    
    // Event-Handler für Verbindungsfehler
    ws.onerror = (error) => {
        console.error('WebSocket-Fehler:', error);
    };
    
    // Event-Handler für eingehende Nachrichten
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('WebSocket-Nachricht empfangen:', data);

            if (data.type === 'fader') {
                // Aktualisiere Kanalfader
                const fader = document.querySelector(`.fader[data-channel="${data.channel}"]`);
                if (fader) {
                    const thumb = fader.querySelector('.fader-thumb');
                    thumb.dataset.value = data.value;
                    const height = fader.getBoundingClientRect().height;
                    const y = height * (1 - data.value);
                    thumb.style.top = `${y}px`;
                    console.log(`Fader ${data.channel} aktualisiert auf ${data.value}`);
                }
                
                // Spezielle Behandlung für Master-Fader
                if (data.channel === 'master') {
                    const masterFader = document.querySelector('.master-fader');
                    if (masterFader) {
                        const thumb = masterFader.querySelector('.fader-thumb');
                        thumb.dataset.value = data.value;
                        const height = masterFader.getBoundingClientRect().height;
                        const y = height * (1 - data.value);
                        thumb.style.top = `${y}px`;
                        console.log(`Master-Fader aktualisiert auf ${data.value}`);
                    }
                }
            } else if (data.type === 'mute') {
                // Aktualisiere Mute-Button Status
                const button = document.querySelector(`.mute-button[data-channel="${data.channel}"]`);
                if (button) {
                    button.classList.toggle('muted', data.value === 0);
                } else if (data.channel === 'master') {
                    document.querySelector('.master-mute').classList.toggle('muted', data.value === 0);
                }
            } else if (data.type === 'meters') {
                console.log('Meter-Daten empfangen:', data);
                updateMeters(data.left, data.right);
            }
        } catch (e) {
            console.error('Fehler bei der Verarbeitung der Nachricht:', e, event.data);
        }
    };
}

// Meter-Aktualisierungsfunktionen
function updateMeters(leftDb, rightDb) {
    // Konvertiere dB in Prozent (0dB = 100%, -48dB = 0%)
    function dbToPercent(db) {
        // Stelle sicher, dass db eine Zahl ist und nicht -inf
        db = parseFloat(db);
        if (isNaN(db) || db === Number.NEGATIVE_INFINITY) {
            return 0;
        }
        
        if (db <= -48) return 0;
        if (db >= 0) return 100;
        // Lineare Interpolation zwischen -48dB (0%) und 0dB (100%)
        return (db + 48) * (100 / 48);
    }

    const leftMeter = document.querySelector('.meter-bar.left-meter');
    const rightMeter = document.querySelector('.meter-bar.right-meter');
    
    if (leftMeter && rightMeter) {
        // Aktualisierungsfunktion für einzelnen Meter
        const updateMeter = (meter, db) => {
            const height = dbToPercent(db);
            meter.style.height = `${height}%`;
            
            // Entferne alte Klassen
            meter.classList.remove('low', 'medium', 'high');
            
            // Füge neue Klasse basierend auf dB-Wert hinzu
            if (db >= -6) {  // 0 bis -6 dB: Rot
                meter.classList.add('high');
            } else if (db >= -12) {  // -6 bis -12 dB: Gelb
                meter.classList.add('medium');
            } else {  // unter -12 dB: Grün
                meter.classList.add('low');
            }
        };
        
        // Aktualisiere beide Meter
        updateMeter(leftMeter, leftDb);
        updateMeter(rightMeter, rightDb);
    } else {
        console.error('Meter-Elemente nicht gefunden!');
    }
}

// Definition der verfügbaren Audiokanäle
const channels = [
    { name: "Headset 1", id: "Headset 1" },
    { name: "Headset 2", id: "Headset 2" },
    { name: "Hand 1", id: "Hand 1" },
    { name: "Hand 2", id: "Hand 2" },
    { name: "HDMI", id: "HDMI" },
    { name: "Regie", id: "Regie" }
];

// Funktion zum Erstellen eines Kanalstreifens im UI
function createChannelStrip(channel) {
    const stripDiv = document.createElement('div');
    stripDiv.className = 'channel-strip';
    stripDiv.innerHTML = `
        <div class="channel-name">${channel.name}</div>
        <div class="fader-container">
            <div class="marks"></div>
            <div class="fader" data-channel="${channel.id}">
                <div class="fader-thumb" data-value="0"></div>
            </div>
        </div>
        <button class="mute-button" data-channel="${channel.id}">MUTE</button>
    `;
    return stripDiv;
}

// Initialisierung der Kanalstreifen
function initializeChannels() {
    const container = document.querySelector('.channels-container');
    channels.forEach(channel => {
        container.appendChild(createChannelStrip(channel));
    });
}

// Event-Listener Setup für alle Bedienelemente
function setupEventListeners() {
    // Funktion zum Aktualisieren des Fader-Werts
    function updateFaderValue(fader, y) {
        const rect = fader.getBoundingClientRect();
        const height = rect.height;
        const normalizedY = Math.max(0, Math.min(height, y - rect.top));
        const value = Math.max(0, Math.min(1, 1 - (normalizedY / height)));
        
        // Aktualisiere die Position des Thumbs
        const thumb = fader.querySelector('.fader-thumb');
        thumb.style.top = `${normalizedY}px`;
        thumb.dataset.value = value;

        // Sende den Wert an den Server
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'fader',
                channel: fader.dataset.channel,
                value: value
            }));
        }
    }

    // Funktion zum Initialisieren der Fader-Positionen
    function initializeFaderPosition(fader) {
        const thumb = fader.querySelector('.fader-thumb');
        const value = parseFloat(thumb.dataset.value);
        const height = fader.getBoundingClientRect().height;
        const y = height * (1 - value);
        thumb.style.top = `${y}px`;
    }

    // Event-Handler für Maus-Events
    function handleMouseDown(e) {
        const fader = e.target.closest('.fader');
        if (!fader) return;

        e.preventDefault();
        const thumb = fader.querySelector('.fader-thumb');
        thumb.classList.add('dragging');

        function handleMouseMove(e) {
            updateFaderValue(fader, e.clientY);
        }

        function handleMouseUp() {
            thumb.classList.remove('dragging');
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        }

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
        
        // Initialer Update
        updateFaderValue(fader, e.clientY);
    }

    // Event-Handler für Touch-Events
    function handleTouchStart(e) {
        const fader = e.target.closest('.fader');
        if (!fader) return;

        e.preventDefault();
        const thumb = fader.querySelector('.fader-thumb');
        thumb.classList.add('dragging');

        function handleTouchMove(e) {
            const touch = e.touches[0];
            updateFaderValue(fader, touch.clientY);
        }

        function handleTouchEnd() {
            thumb.classList.remove('dragging');
            document.removeEventListener('touchmove', handleTouchMove);
            document.removeEventListener('touchend', handleTouchEnd);
            document.removeEventListener('touchcancel', handleTouchEnd);
        }

        document.addEventListener('touchmove', handleTouchMove, { passive: false });
        document.addEventListener('touchend', handleTouchEnd);
        document.addEventListener('touchcancel', handleTouchEnd);
        
        // Initialer Update
        const touch = e.touches[0];
        updateFaderValue(fader, touch.clientY);
    }

    // Initialisiere alle Fader
    document.querySelectorAll('.fader').forEach(fader => {
        // Setze initiale Position
        initializeFaderPosition(fader);
        
        // Event-Listener für Maus und Touch
        fader.addEventListener('mousedown', handleMouseDown);
        fader.addEventListener('touchstart', handleTouchStart, { passive: false });
    });

    // Mute-Button Event-Listener
    document.querySelectorAll('.mute-button').forEach(button => {
        button.addEventListener('click', (e) => {
            const channel = e.target.dataset.channel;
            const isMuted = e.target.classList.toggle('muted');
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'mute',
                    channel: channel,
                    value: isMuted ? 0 : 1
                }));
            }
        });
    });

    // Gong-Button Event-Listener
    document.getElementById('gongButton').addEventListener('click', async () => {
        try {
            const response = await fetch('/play-gong', {
                method: 'POST'
            });
            const data = await response.json();
            if (data.status !== 'success') {
                console.error('Fehler beim Abspielen des Gongs:', data.message);
            }
        } catch (error) {
            console.error('Fehler beim Abspielen des Gongs:', error);
        }
    });
}

// Initialisierung beim Laden der Seite
document.addEventListener('DOMContentLoaded', () => {
    // Verbinde WebSocket
    connectWebSocket();
});
