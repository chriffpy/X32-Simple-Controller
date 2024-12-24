let ws = null;
let reconnectTimeout = null;
const RECONNECT_DELAY = 1000; // 1 Sekunde
const MAX_RECONNECT_DELAY = 5000; // Maximale Verzögerung 5 Sekunden
let currentReconnectDelay = RECONNECT_DELAY;

function connectWebSocket() {
    if (ws !== null && ws.readyState !== WebSocket.CLOSED) {
        return;
    }
    
    clearTimeout(reconnectTimeout);
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    
    ws.onopen = () => {
        console.log('Connected to server');
        currentReconnectDelay = RECONNECT_DELAY; // Reset delay on successful connection
        clearTimeout(reconnectTimeout);
        
        // Request initial values
        ws.send(JSON.stringify({
            type: 'request_initial_values'
        }));
        
        initializeChannels();
        setupEventListeners();
    };
    
    ws.onclose = () => {
        console.log('Disconnected from server - attempting to reconnect...');
        clearTimeout(reconnectTimeout);
        
        // Exponential backoff with max delay
        currentReconnectDelay = Math.min(currentReconnectDelay * 1.5, MAX_RECONNECT_DELAY);
        reconnectTimeout = setTimeout(connectWebSocket, currentReconnectDelay);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('WebSocket message received:', data);

            if (data.type === 'fader') {
                // Update channel fader
                const fader = document.querySelector(`input[data-channel="${data.channel}"]`);
                if (fader) {
                    fader.value = data.value;
                }
                
                // Update mute button state
                if (data.channel !== 'master') {
                    const muteButton = document.querySelector(`button[data-channel="${data.channel}"]`);
                    if (muteButton) {
                        muteButton.classList.toggle('muted', data.value === 0);
                    }
                } else {
                    const masterMute = document.querySelector('.master-mute');
                    if (masterMute) {
                        masterMute.classList.toggle('muted', data.value === 0);
                    }
                }
            } else if (data.type === 'mute') {
                // Update mute button state
                const button = document.querySelector(`button[data-channel="${data.channel}"]`);
                if (button) {
                    button.classList.toggle('muted', data.value === 0);
                } else if (data.channel === 'master') {
                    document.querySelector('.master-mute').classList.toggle('muted', data.value === 0);
                }
            } else if (data.type === 'meters') {
                console.log('Meter data received:', data.left, data.right);
                updateMeters(data.left, data.right);
            }
        } catch (e) {
            console.error('Error processing message:', e);
        }
    };
}

// Meter Handling
function updateMeters(leftDb, rightDb) {
    // Konvertiere dB in Prozent (0dB = 100%, -48dB = 0%)
    function dbToPercent(db) {
        if (db <= -48) return 0;
        if (db >= 0) return 100;
        // Lineare Interpolation zwischen -48dB (0%) und 0dB (100%)
        return (db + 48) * (100 / 48);
    }

    const leftMeter = document.querySelector('.left-meter');
    const rightMeter = document.querySelector('.right-meter');
    
    console.log('Updating meters:', leftDb, rightDb);
    console.log('Meter elements:', leftMeter, rightMeter);
    console.log('Calculated heights:', `${dbToPercent(leftDb)}%`, `${dbToPercent(rightDb)}%`);

    if (leftMeter && rightMeter) {
        leftMeter.style.height = `${dbToPercent(leftDb)}%`;
        rightMeter.style.height = `${dbToPercent(rightDb)}%`;
    } else {
        console.error('Meter elements not found!');
    }
}

const channels = [
    { name: "Headset 1", id: "Headset 1" },
    { name: "Headset 2", id: "Headset 2" },
    { name: "Hand 1", id: "Hand 1" },
    { name: "Hand 2", id: "Hand 2" },
    { name: "HDMI", id: "HDMI" },
    { name: "Regie", id: "Regie" }
];

function createChannelStrip(channel) {
    const stripDiv = document.createElement('div');
    stripDiv.className = 'channel-strip';
    stripDiv.innerHTML = `
        <div class="channel-name">${channel.name}</div>
        <div class="fader-container">
            <div class="marks"></div>
            <input type="range" class="fader" 
                   data-channel="${channel.id}"
                   min="0" max="1" step="0.01" value="0" 
                   orient="vertical">
        </div>
        <button class="mute-button" data-channel="${channel.id}">MUTE</button>
    `;
    return stripDiv;
}

function initializeChannels() {
    const container = document.querySelector('.channels-container');
    channels.forEach(channel => {
        container.appendChild(createChannelStrip(channel));
    });
}

function setupEventListeners() {
    // Channel Faders
    document.querySelectorAll('.fader:not(.master-fader)').forEach(fader => {
        fader.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            const channel = e.target.dataset.channel;
            ws.send(JSON.stringify({
                type: 'fader',
                channel: channel,
                value: value
            }));
        });
    });

    // Master Fader
    document.querySelector('.master-fader').addEventListener('input', (e) => {
        const value = parseFloat(e.target.value);
        ws.send(JSON.stringify({
            type: 'fader',
            channel: 'master',
            value: value
        }));
    });

    // Channel Mute Buttons
    document.querySelectorAll('.mute-button:not(.master-mute)').forEach(button => {
        button.addEventListener('click', (e) => {
            const channel = e.target.dataset.channel;
            const isMuted = e.target.classList.toggle('muted');
            ws.send(JSON.stringify({
                type: 'mute',
                channel: channel,
                value: isMuted ? 0 : 1
            }));
        });
    });

    // Master Mute Button
    document.querySelector('.master-mute').addEventListener('click', (e) => {
        const isMuted = e.target.classList.toggle('muted');
        ws.send(JSON.stringify({
            type: 'mute',
            channel: 'master',
            value: isMuted ? 0 : 1
        }));
    });

    document.getElementById('gongButton').addEventListener('click', async () => {
        try {
            const response = await fetch('/play-gong', {
                method: 'POST'
            });
            const data = await response.json();
            if (data.status !== 'success') {
                console.error('Failed to play gong:', data.message);
            }
        } catch (error) {
            console.error('Error playing gong:', error);
        }
    });
}

// Initialisierung
document.addEventListener('DOMContentLoaded', () => {
    // Connect WebSocket
    connectWebSocket();
});
