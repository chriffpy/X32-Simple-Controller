from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pythonosc import udp_client, dispatcher, osc_server
import json
import logging
import asyncio
import time
import socket
from threading import Thread
import queue
from collections import namedtuple
from config import X32_IP, X32_PORT, CHANNEL_MAPPING, LOCAL_PORT

# Logging konfigurieren
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
connected_clients = []

ReceivedMessage = namedtuple("ReceivedMessage", "address, tags, data")

class X32Dispatcher(dispatcher.Dispatcher):
    def __init__(self, queue):
        super().__init__()
        self._queue = queue

    def handle_message(self, address, *args):
        msg = ReceivedMessage(address=address, tags=None, data=args)
        self._queue.put(msg)
        logger.debug(f"Received OSC message: {address} {args}")

class X32Connection:
    def __init__(self, x32_address, server_port, timeout=10):
        self._timeout = timeout
        self._input_queue = queue.Queue()
        self._connected = False
        self._x32_address = x32_address
        self._server_port = server_port
        
        logger.info(f"Initializing X32 connection to {x32_address}:{X32_PORT}")
        
        try:
            # Setup dispatcher and server
            self._dispatcher = X32Dispatcher(self._input_queue)
            
            # Create server with fixed port
            self._server = osc_server.ThreadingOSCUDPServer(
                ("0.0.0.0", server_port), 
                self._dispatcher
            )
            logger.info(f"OSC server listening on 0.0.0.0:{server_port}")
            
            # Create client that sends from the same port
            self._client = udp_client.SimpleUDPClient(x32_address, X32_PORT)
            self._client._sock.bind(("0.0.0.0", server_port))
            logger.info("OSC client created and bound to server port")
            
            # Start server thread
            self._server_thread = Thread(target=self._server.serve_forever)
            self._server_thread.daemon = True
            self._server_thread.start()
            logger.info("OSC server thread started")
            
            # Initialize connection
            self._initialize_connection()
            
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            raise

    def _initialize_connection(self):
        """Initialize connection to X32"""
        max_retries = 5
        retry_count = 0
        
        logger.info("Starting X32 connection initialization")
        
        while not self._connected and retry_count < max_retries:
            try:
                logger.debug(f"Connection attempt {retry_count + 1}")
                
                # Clear queue before sending info request
                while True:
                    try:
                        self._input_queue.get_nowait()
                    except queue.Empty:
                        break
                
                # Send info request
                logger.debug("Sending /info request")
                self._client.send_message("/info", None)
                
                try:
                    # Wait for response
                    logger.debug("Waiting for /info response")
                    response = self._input_queue.get(timeout=self._timeout)
                    if response:
                        logger.info(f"Connected to X32: {response}")
                        self._connected = True
                        
                        # Send initial xremote
                        logger.debug("Sending initial /xremote")
                        self._client.send_message("/xremote", None)
                        time.sleep(0.1)  # Give X32 time to process
                        return
                except queue.Empty:
                    logger.warning("No response to /info request")
                
            except Exception as e:
                logger.error(f"Connection attempt {retry_count + 1} failed: {e}")
            
            retry_count += 1
            if retry_count < max_retries:
                logger.info(f"Retrying in 1 second... (attempt {retry_count + 1}/{max_retries})")
                time.sleep(1)
        
        if not self._connected:
            logger.error(f"Failed to connect to X32 at {self._x32_address}:{X32_PORT}")
            raise ConnectionError(f"Could not connect to X32 at {self._x32_address}:{X32_PORT}")

    def get_value(self, path):
        """Get value from X32"""
        if not self._connected:
            logger.error("Not connected to X32")
            return None
            
        # Clear queue first
        while True:
            try:
                self._input_queue.get_nowait()
            except queue.Empty:
                break            
        
        # Send request
        logger.debug(f"Requesting value for {path}")
        self._client.send_message(path, None)
        time.sleep(0.01)  # Give X32 time to respond
        
        try:
            response = self._input_queue.get(timeout=self._timeout)
            if response.data:
                logger.debug(f"Received value for {path}: {response.data[0]}")
                return response.data[0]  # Return first value
            logger.warning(f"Empty response for {path}")
            return None
        except queue.Empty:
            logger.error(f"Timeout getting value for {path}")
            return None

    def set_value(self, path, value):
        """Set value on X32"""
        if not self._connected:
            logger.error("Not connected to X32")
            return
            
        logger.debug(f"Setting {path} to {value}")
        self._client.send_message(path, value)

    def maintain_connection(self):
        """Maintain connection to X32"""
        while True:
            if self._connected:
                try:
                    self._client.send_message("/xremote", None)
                    time.sleep(9)
                except:
                    logger.error("Error sending /xremote")
                    self._connected = False
            else:
                try:
                    logger.info("Connection lost, attempting to reconnect...")
                    self._initialize_connection()
                except:
                    logger.error("Failed to reconnect to X32")
                time.sleep(1)

    def request_initial_values(self):
        """Request current values for all channels"""
        if not self._connected:
            logger.error("Not connected to X32")
            return
            
        logger.info("Requesting initial channel values")
        
        # Wait a bit to ensure connection is stable
        time.sleep(0.5)
        
        for channel_name, channel_num in CHANNEL_MAPPING.items():
            # Format channel number with leading zero
            ch_num = f"{channel_num:02d}"
            
            # Request fader value
            fader_path = f"/ch/{ch_num}/mix/fader"
            fader_value = self.get_value(fader_path)
            if fader_value is not None:
                logger.info(f"Initial fader value for {channel_name}: {fader_value}")
            
            # Request mute state
            mute_path = f"/ch/{ch_num}/mix/on"
            mute_value = self.get_value(mute_path)
            if mute_value is not None:
                logger.info(f"Initial mute value for {channel_name}: {mute_value}")
            
            # Small delay between requests
            time.sleep(0.1)

        # Request master values
        master_fader = self.get_value("/main/st/mix/fader")
        if master_fader is not None:
            logger.info(f"Initial master fader value: {master_fader}")
        
        time.sleep(0.1)
        
        master_mute = self.get_value("/main/st/mix/on")
        if master_mute is not None:
            logger.info(f"Initial master mute value: {master_mute}")

# Global X32 connection
logger.info(f"Creating X32 connection to {X32_IP}:{X32_PORT}")
x32 = X32Connection(X32_IP, LOCAL_PORT)

# Start connection maintenance thread
logger.info("Starting connection maintenance thread")
connection_thread = Thread(target=x32.maintain_connection)
connection_thread.daemon = True
connection_thread.start()

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")
    connected_clients.append(websocket)
    
    try:
        # Send initial values when client connects
        x32.request_initial_values()
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if "type" in message:
                if message["type"] == "fader":
                    channel = message["channel"]
                    value = message["value"]
                    
                    if channel == "master":
                        path = "/main/st/mix/fader"
                    else:
                        channel_num = CHANNEL_MAPPING[channel]
                        path = f"/ch/{channel_num:02d}/mix/fader"
                    
                    x32.set_value(path, float(value))
                    
                elif message["type"] == "mute":
                    channel = message["channel"]
                    value = message["value"]
                    
                    if channel == "master":
                        path = "/main/st/mix/on"
                    else:
                        channel_num = CHANNEL_MAPPING[channel]
                        path = f"/ch/{channel_num:02d}/mix/on"
                    
                    x32.set_value(path, 1 if value else 0)
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        logger.info("WebSocket client disconnected")
        connected_clients.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server")
    uvicorn.run(app, host="0.0.0.0", port=8000)
