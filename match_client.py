from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QTimer
import sys
import json
import logging
import requests
import threading
import time
import uvicorn
import websocket
from queue import Queue

# ---------- Setup ----------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OVERWOLF_LOCALHOST_URL = "http://localhost:54284/json"
LOCALHOST_URL = "http://localhost:5172/receive"

url_queue = Queue()


# ---------- GUI ----------
class BrowserWindow(QMainWindow):
    def __init__(self, url):
        super().__init__()
        self.setWindowTitle("Match Viewer")

        self.browser = QWebEngineView()
        self.browser.load(QUrl(url))
        self.browser.setZoomFactor(0.8)  # Zoom out slightly (default is 1.0)

        self.setCentralWidget(self.browser)
        self.resize(1800, 1200)  # Increase window size
        self.show()



def launch_browser_window(url):
    url_queue.put(url)

browser_window = None



def check_url_queue():
    global browser_window
    if not url_queue.empty():
        url = url_queue.get()
        if browser_window:
            browser_window.close()
        browser_window = BrowserWindow(url)
        browser_window.show()


# ---------- FastAPI Endpoint ----------
@app.post("/receive")
async def receiver(request: Request):
    try:
        data = await request.json()
        logger.info(f"Received data: {data}")

        if 'content' in data:
            url = data['content']
            logger.info(f"Dashboard URL: {url}")
            launch_browser_window(url)

        return {"status": "Success!", "received": data, "url_opened": True}
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {"status": "Error", "message": str(e)}


# ---------- Overwolf Injection ----------
def inject_javascript():
    try:
        targets = requests.get(OVERWOLF_LOCALHOST_URL).json()
        target_ws_url = next(
            (t["webSocketDebuggerUrl"] for t in targets if t["title"] == "Overwolf GameEvents Provider index"), None)

        if target_ws_url:
            ws = websocket.create_connection(target_ws_url)
            js_code = f"""
                (function() {{
                    console.log = m => {{
                        if (m.startsWith("[PLUGIN INFO]")) {{
                            const jsonString = m.substring(m.indexOf('{{'));
                            try {{
                                const parsedMsg = JSON.parse(jsonString);
                                if (['player_list_log'].includes(parsedMsg.key)) {{
                                    const players = JSON.parse(parsedMsg.value);

                                    const identifiers = players.map(p => {{
                                        return {{ [p.profile_id]: p.team_id }};
                                    }});

                                    const encoded = encodeURIComponent(JSON.stringify(identifiers));
                                    const link = "https://siege-spider-dashboard.vercel.app/match?identifiers=" + encoded;

                                    const payload = {{
                                        content: link
                                    }};

                                    fetch("{LOCALHOST_URL}", {{
                                        method: 'POST',
                                        headers: {{
                                            'Content-Type': 'application/json'
                                        }},
                                        body: JSON.stringify(payload)
                                    }});
                                }}
                            }} catch (e) {{
                                console.error('Failed to parse JSON:', e);
                            }}
                        }}
                    }};
                }})();
            """

            ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": js_code, "returnByValue": False}
            }))
            ws.close()
            return "JavaScript injected successfully."
    except (requests.RequestException, websocket.WebSocketException) as e:
        return f"Error: {e}"
    return "Failed to Inject. Overwolf not running?"


# ---------- Main ----------
if __name__ == "__main__":
    def run_server():
        inject_result = inject_javascript()
        logger.info(inject_result)
        uvicorn.run("__main__:app", host="0.0.0.0", port=5172, log_level="info")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    time.sleep(3)
    logger.info("=" * 50)
    logger.info("JavaScript injected! Server is running...")
    logger.info("Localhost server logs will appear below:")
    logger.info("Press Ctrl+C to exit")
    logger.info("=" * 50 + "\n")

    qt_app = QApplication(sys.argv)

    timer = QTimer()
    timer.timeout.connect(check_url_queue)
    timer.start(500)
    url_queue.put("https://siege-spider-dashboard.vercel.app")
    sys.exit(qt_app.exec_())
