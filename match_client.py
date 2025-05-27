from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
import json
import logging
import requests
import threading
import time
import uvicorn
import webbrowser
import websocket

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS -- overwolf frontend dev client seems to always send a pre-req options request...
    allow_headers=["*"],  # Allow all headers
)

OVERWOLF_LOCALHOST_URL = "http://localhost:54284/json"
LOCALHOST_URL = "http://localhost:5172/receive"

@app.post("/receive")
async def receiver(request: Request):
    try:
        data = await request.json()
        logger.info(f"Received data: {data}")

        # TODO: Refactor to take list of profile ids as input and do the url building within the endpoint to make the javascript injection simpler and lighter weigh
        if 'content' in data:
            url = data['content']
            logger.info(f"Dashboard URL: {url}")

            # open the URL in the default browser
            try:
                webbrowser.open(url)
                logger.info(f"Opened URL in browser: {url}")
            except Exception as browser_error:
                logger.info(f"Failed to open URL in browser: {browser_error}")

        return {"status": "Success!", "received": data, "url_opened": True}
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return {"status": "Error", "message": str(e)}

def start_server():
    """Start the FastAPI server in a separate thread"""
    uvicorn.run("__main__:app", host="0.0.0.0", port=5172, log_level="info")

def inject_javascript():
    """Inject javascript into overwolf dev tools to intercept rainbow six siege data"""
    try:
        targets = requests.get(OVERWOLF_LOCALHOST_URL).json()
        target_ws_url = next(
            (t["webSocketDebuggerUrl"] for t in targets if t["title"] == "Overwolf GameEvents Provider index"), None)

        if target_ws_url:
            localhost_url = "http://localhost:5172/receive"

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

                                    fetch("{localhost_url}", {{
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


if __name__ == "__main__":
    logger.info("Starting local server...")

    # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Wait a moment for the server to start
    time.sleep(3)
    logger.info("Server started. Injecting JavaScript...")

    # Now inject the javascript into overwolf
    result = inject_javascript()
    logger.info(result)

    logger.info("\n" + "="*50)
    logger.info("JavaScript injected! Server is running...")
    logger.info("Localhost server logs will appear below:")
    logger.info("Press Ctrl+C to exit")
    logger.info("="*50 + "\n")

    try:
        # Keep the main thread alive so we can see FastAPI logs
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        logger.info("Goodbye!")

