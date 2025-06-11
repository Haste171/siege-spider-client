import sys

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

CURRENT_VERSION = "1.0.1"
OVERWOLF_LOCALHOST_URL = "http://localhost:54284/json"
LOCALHOST_URL = "http://localhost:5172/receive"
SIEGE_SPIDER_DASHBOARD_BASE_URL = "https://siege-spider-dashboard.vercel.app"
SIEGE_SPIDER_API_BASE_URL = "https://siege-spider-api-6d251bf857a7.herokuapp.com"


@app.post("/receive")
async def receiver(request: Request):
    try:
        data = await request.json()
        logger.info(f"Received data: {data}")

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

def check_version():
    url = SIEGE_SPIDER_API_BASE_URL + "/client/version"
    resp = requests.get(url)
    if resp.status_code == 200:
        resp = resp.json()
        if resp.get('current_version') == CURRENT_VERSION:
            logger.info(f"Loaded client version: {CURRENT_VERSION}")
        else:
            outdated_url = SIEGE_SPIDER_DASHBOARD_BASE_URL + "/outdated"
            webbrowser.open(outdated_url)
            logger.info("Siege Spider client outdated!")
            sys.exit(1)

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
            siege_spider_api_base_url = SIEGE_SPIDER_API_BASE_URL
            siege_spider_dashboard_url = SIEGE_SPIDER_DASHBOARD_BASE_URL

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

                                    // First, call the ingestion endpoint to get the match ID
                                    fetch("{siege_spider_api_base_url}/ingest/match", {{
                                        method: 'POST',
                                        headers: {{
                                            'Content-Type': 'application/json'
                                        }},
                                        body: JSON.stringify({{ identifiers: identifiers }})
                                    }})
                                    .then(response => {{
                                        if (!response.ok) {{
                                            throw new Error(`HTTP error! status: ${{response.status}}`);
                                        }}
                                        return response.json();
                                    }})
                                    .then(data => {{
                                        // Extract the match ID from the response
                                        const matchId = data.id;
                                        
                                        // Create the new URL format with the match ID
                                        const link = `{siege_spider_dashboard_url}/match/${{matchId}}`;

                                        // Send the link to the localhost endpoint
                                        const payload = {{
                                            content: link
                                        }};

                                        return fetch("{localhost_url}", {{
                                            method: 'POST',
                                            headers: {{
                                                'Content-Type': 'application/json'
                                            }},
                                            body: JSON.stringify(payload)
                                        }});
                                    }})
                                    .then(response => {{
                                        console.log('Successfully sent match link to localhost');
                                    }})
                                    .catch(error => {{
                                        console.error('Error processing match data:', error);
                                        
                                        // Fallback: send error information to localhost
                                        const errorPayload = {{
                                            content: `Error processing match: ${{error.message}}`
                                        }};
                                        
                                        fetch("{localhost_url}", {{
                                            method: 'POST',
                                            headers: {{
                                                'Content-Type': 'application/json'
                                            }},
                                            body: JSON.stringify(errorPayload)
                                        }});
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
    check_version()
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

