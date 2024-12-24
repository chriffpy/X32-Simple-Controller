const channels = [
    { name: "Headset 1", id: "Headset 1" },
    { name: "Headset 2", id: "Headset 2" },
    { name: "Hand 1", id: "Hand 1" },
    { name: "Hand 2", id: "Hand 2" },
    { name: "HDMI", id: "HDMI" },
    { name: "Regie", id: "Regie" }
];

const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws`);

function createChannelStrip(channel) {
    const stripDiv = document.createElement('div');
    stripDiv.className = 'channel-strip';
    stripDiv.innerHTML = `
        <div class="channel-name">${channel.name}</div>
        <div class="fader-container">
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
            type: 'master',
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
            type: 'master_mute',
            value: isMuted ? 0 : 1
        }));
    });
}

// Handle updates from the server
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'fader') {
        // Update channel fader
        const fader = document.querySelector(`input[data-channel="${data.channel}"]`);
        if (fader) {
            fader.value = data.value;
        } else if (data.channel === 'master') {
            document.querySelector('.master-fader').value = data.value;
        }
    } else if (data.type === 'mute') {
        // Update mute button state
        const button = document.querySelector(`button[data-channel="${data.channel}"]`);
        if (button) {
            button.classList.toggle('muted', data.value === 0);
        } else if (data.channel === 'master') {
            document.querySelector('.master-mute').classList.toggle('muted', data.value === 0);
        }
    }
};

ws.onopen = () => {
    console.log('Connected to server');
    initializeChannels();
    setupEventListeners();
    
    // Request initial fader values
    ws.send(JSON.stringify({
        type: 'request_initial_values'
    }));
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('Disconnected from server');
};
