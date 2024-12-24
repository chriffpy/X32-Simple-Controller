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
from queue import Queue
import playsound
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

# Logging konfigurieren
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
connected_clients = []
update_queue = Queue()

# Broadcast worker thread
async def broadcast_message(message: str):
    if not message:
        return
        
    # Convert to list to avoid modification during iteration
    clients = list(connected_clients)
    for client in clients:
        try:
            await client.send_text(message)
        except Exception as e:
            logger.error(f"Error sending to client: {e}")
            if client in connected_clients:
                connected_clients.remove(client)

def broadcast_worker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while True:
        message = update_queue.get()
        if message is None:
            break
            
        # Schedule coroutine in the event loop
        loop.run_until_complete(broadcast_message(message))

# Start broadcast worker thread
broadcast_thread = Thread(target=broadcast_worker, daemon=True)
broadcast_thread.start()

ReceivedMessage = namedtuple("ReceivedMessage", "address, tags, data")

class X32Dispatcher(dispatcher.Dispatcher):
    def __init__(self, queue):
        super().__init__()
        self._queue = queue
        self._values = {}  # Store latest values
        
        # Add specific handlers
        self.map("/xinfo", self._handle_xinfo)
        self.map("/ch/*/mix/fader", self._handle_fader)
        self.map("/main/st/mix/fader", self._handle_fader)
        
    def _handle_xinfo(self, address, *args):
        logger.debug(f"Received XINFO response: {args}")
        self._queue.put({"address": address, "args": args})
        
    def _handle_fader(self, address, *args):
        logger.debug(f"Received fader update: {address} = {args}")
        value = args[0] if args else None
        self._values[address] = value
        
        # Create WebSocket update message
        if address == "/main/st/mix/fader":
            channel = "master"
        else:
            # Extract channel number from path
            channel_num = int(address.split('/')[2])
            # Find channel name from mapping
            channel = next((name for name, num in CHANNEL_MAPPING.items() if num == channel_num), None)
            if channel is None:
                return
        
        # Send update to all connected clients
        message = {
            "type": "fader",
            "channel": channel,
            "value": value
        }
        
        # Put message in queue instead of direct send
        update_queue.put(json.dumps(message))
        
    def get_value(self, path):
        """Get latest value from cache"""
        return self._values.get(path)
        
    def handle_message(self, address, *args):
        logger.debug(f"Received OSC message: {address} {args}")
        self._queue.put({"address": address, "args": args})

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
            
            # Create server
            self._server = osc_server.ThreadingOSCUDPServer(
                ("0.0.0.0", server_port), 
                self._dispatcher
            )
            logger.info(f"OSC server created on port {server_port}")
            
            # Get the socket from server and enable address reuse
            self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Create client and use server's socket
            self._client = udp_client.SimpleUDPClient(x32_address, X32_PORT)
            self._client._sock = self._server.socket
            logger.info("OSC client created using server socket")
            
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
                
                # Send xinfo request with exact format
                logger.debug("Sending /xinfo request")
                self._client.send_message("/xinfo", [","])  # Adding the "," type tag as seen in Wireshark
                
                try:
                    # Wait for response
                    logger.debug("Waiting for /xinfo response")
                    response = self._input_queue.get(timeout=self._timeout)
                    if response and response.get("address") == "/xinfo":
                        ip, name, model, fw = response["args"]
                        logger.info(f"Connected to X32: {model} at {ip} (Name: {name}, Firmware: {fw})")
                        self._connected = True
                        
                        # Subscribe to meter updates with exact format matching X32 Edit
                        self._client.send_message("/xremote", [","])  # Adding type tag "," with null padding
                        time.sleep(0.1)  # Give X32 time to process

                        # Subscribe to fader updates
                        logger.info("Subscribing to fader updates")
                        
                        # Subscribe to channel faders
                        fader_paths = []
                        for channel_num in CHANNEL_MAPPING.values():
                            fader_paths.append(f"/ch/{channel_num:02d}/mix/fader")
                        
                        # Add master fader
                        fader_paths.append("/main/st/mix/fader")
                        
                        # Create subscription message with type tags
                        type_tags = ["s"] * len(fader_paths) + ["i", "i", "i"]
                        type_tag_string = "," + "".join(type_tags)
                        
                        # Send subscription
                        args = ["hidden/faders"] + fader_paths + [0, 0, 50]  # 50ms update interval
                        self._client.send_message("/formatsubscribe", [type_tag_string] + args)
                        
                        # Also subscribe to general state updates as seen in Wireshark
                        self._client.send_message("/formatsubscribe", 
                            [",sssssssssssssssssssssiii", 
                             "hidden/states",
                             "/-stat/tape/state",
                             "/-usb/path",
                             "/-usb/title",
                             "/-stat/tape/etime",
                             "/-stat/tape/rtime",
                             "/-stat/aes50/state",
                             "/-stat/aes50/A",
                             "/-stat/aes50/B",
                             "/-show/prepos/current",
                             "/-stat/usbmounted",
                             "/-usb/dir/dirpos",
                             "/-usb/dir/maxpos",
                             "/-stat/xcardtype",
                             "/-stat/xcardsync",
                             "/-stat/rtasource",
                             "/-stat/talk/A",
                             "/-stat/talk/B",
                             "/-stat/osc/on",
                             "/-stat/keysolo",
                             "/-stat/urec/state",
                             "/-stat/urec/etime",
                             "/-stat/urec/rtime",
                             0, 0, 4])
                        
                        return
                except queue.Empty:
                    logger.warning("No response to /xinfo request")
                
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
            
        # Try to get value from dispatcher cache first
        value = self._dispatcher.get_value(path)
        if value is not None:
            return value
            
        # If not in cache, request it
        logger.debug(f"Requesting value for {path}")
        self._client.send_message(path, [","])
        
        try:
            response = self._input_queue.get(timeout=self._timeout)
            if response.get("args"):
                logger.debug(f"Received value for {path}: {response['args'][0]}")
                return response["args"][0]  # Return first value
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
        logger.info("Requesting initial channel values")
        
        # Request main fader
        self._client.send_message("/main/st/mix/fader", None)
        
        # Request channel faders
        for channel_num in CHANNEL_MAPPING.values():
            path = f"/ch/{channel_num:02d}/mix/fader"
            self._client.send_message(path, None)
            
        # Small delay to allow responses to arrive
        time.sleep(0.1)
        
        # Send current values from cache
        for channel_name, channel_num in CHANNEL_MAPPING.items():
            path = f"/ch/{channel_num:02d}/mix/fader"
            value = self._dispatcher.get_value(path)
            if value is not None:
                message = {
                    "type": "fader",
                    "channel": channel_name,
                    "value": value
                }
                update_queue.put(json.dumps(message))
        
        # Send master fader value
        master_value = self._dispatcher.get_value("/main/st/mix/fader")
        if master_value is not None:
            message = {
                "type": "fader",
                "channel": "master",
                "value": master_value
            }
            update_queue.put(json.dumps(message))

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

@app.post("/play-gong")
async def play_gong():
    try:
        import os
        gong_path = os.path.join(os.path.dirname(__file__), 'audio', 'gong.mp3')
        logging.info(f"Attempting to play gong from: {gong_path}")
        
        try:
            from playsound import playsound
        except ImportError as e:
            logging.error(f"Failed to import playsound: {e}")
            return JSONResponse(
                content={"status": "error", "message": "playsound module not available"},
                status_code=500
            )
            
        if not os.path.exists(gong_path):
            logging.error(f"Gong file not found at: {gong_path}")
            return JSONResponse(
                content={"status": "error", "message": "Gong file not found"},
                status_code=404
            )
            
        playsound(gong_path)
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        logging.error(f"Error playing gong: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500
        )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket client connected")
    connected_clients.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "request_initial_values":
                x32.request_initial_values()
            elif message["type"] == "fader":
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
