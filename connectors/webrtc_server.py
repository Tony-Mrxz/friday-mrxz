"""
connectors/webrtc_server.py - Telegram Mini App WebRTC Call Server
FastAPI & WebSockets server serving WebRTC voice streaming and HUD UI.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from config.settings import WEBRTC_PORT
from core.agent_loop import process_user_input
from core.logger import logger
import uvicorn

app = FastAPI(title="Friday WebRTC Call Server")

HUD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>FRIDAY AI Voice Call</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            background-color: #0b0e14;
            color: #00f0ff;
            font-family: 'Segoe UI', Tahoma, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }
        .arc-reactor {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            border: 4px solid #00f0ff;
            box-shadow: 0 0 30px #00f0ff, inset 0 0 30px #00f0ff;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: pulse 2s infinite ease-in-out;
        }
        .inner-core {
            width: 70px;
            height: 70px;
            border-radius: 50%;
            background: #ffffff;
            box-shadow: 0 0 20px #ffffff;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 20px #00f0ff; }
            50% { transform: scale(1.05); box-shadow: 0 0 40px #00f0ff; }
            100% { transform: scale(0.95); box-shadow: 0 0 20px #00f0ff; }
        }
        h1 { margin-top: 30px; letter-spacing: 2px; font-weight: 300; }
        p { color: #88a0b0; }
    </style>
</head>
<body>
    <div class="arc-reactor">
        <div class="inner-core"></div>
    </div>
    <h1>FRIDAY AI CALL</h1>
    <p id="status">Connected to Friday Voice Core</p>

    <script>
        const ws = new WebSocket(`ws://${location.host}/ws`);
        ws.onopen = () => console.log('Connected to Friday WebRTC socket');
        ws.onmessage = (event) => {
            document.getElementById('status').innerText = 'Friday: ' + event.data;
        };
    </script>
</body>
</html>
"""


@app.get("/")
async def get_call_ui():
    return HTMLResponse(content=HUD_HTML)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            response = process_user_input(data)
            await websocket.send_text(response)
    except WebSocketDisconnect:
        logger.info("WebRTC voice call disconnected.")


def run_webrtc_server():
    logger.info(f"🌐 Starting Friday WebRTC Server on port {WEBRTC_PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=WEBRTC_PORT, log_level="warning")
