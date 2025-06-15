from colorama import Fore
from requests.exceptions import ConnectionError
import json
import requests
import subprocess
import sys
import time
import webbrowser
import websocket

CURRENT_VERSION = "1.0.2"
OVERWOLF_LOCALHOST_URL = "http://localhost:54284/json"
LOCALHOST_URL = "http://localhost:5172/receive"
SIEGE_SPIDER_DASHBOARD_BASE_URL = "https://siege-spider-dashboard.vercel.app"
SIEGE_SPIDER_API_BASE_URL = "https://siege-spider-api-6d251bf857a7.herokuapp.com"

def check_version():
    url = SIEGE_SPIDER_API_BASE_URL + "/client/version"
    resp = requests.get(url)
    if resp.status_code == 200:
        resp = resp.json()
        if resp.get('current_version') == CURRENT_VERSION:
            print(f"Client version: {CURRENT_VERSION}\n")
        else:
            outdated_url = SIEGE_SPIDER_DASHBOARD_BASE_URL + "/outdated"
            webbrowser.open(outdated_url)
            print(f"{Fore.RED}Siege Spider client outdated!{Fore.RESET}")
            sys.exit(1)

def print_banner():
    banner_str = """
  ______ _ _______ _______ _______     ______ ______  _ ______  _______ ______  
 / _____) (_______|_______|_______)   / _____|_____ \| (______)(_______|_____ \ 
( (____ | |_____   _   ___ _____     ( (____  _____) ) |_     _ _____   _____) )
 \____ \| |  ___) | | (_  |  ___)     \____ \|  ____/| | |   | |  ___) |  __  / 
 _____) ) | |_____| |___) | |_____    _____) ) |     | | |__/ /| |_____| |  \ \ 
(______/|_|_______)\_____/|_______)  (______/|_|     |_|_____/ |_______)_|   |_|
"""
    print(banner_str)

def retry_protocol():
    if sys.platform.startswith("win"):
        subprocess.run(["start", "overwolf://"], shell=True)
    else:
        print(f"{Fore.RED}\n" + "="*50)
        print("Overwolf is only supported on Windows. Cannot auto-launch. Exiting in 5 seconds!")
        print("="*50 + f"\n{Fore.RESET}")
        time.sleep(5)
        sys.exit(1)

def inject_javascript():
    """Inject javascript into overwolf dev tools to intercept rainbow six siege data"""
    try:
        try:
            targets = requests.get(OVERWOLF_LOCALHOST_URL).json()
        except ConnectionError:
            print(f'{Fore.RED}Failed to access Overwolf localhost!{Fore.RESET}')
            print(f'{Fore.YELLOW}Attempting to launch Overwolf...{Fore.RESET}')
            retry_protocol()
            print(f'{Fore.YELLOW}Sleeping for 10 seconds before retrying...{Fore.RESET}')
            time.sleep(10)

            # Try only once more after sleep — no recursion
            try:
                targets = requests.get(OVERWOLF_LOCALHOST_URL).json()
            except ConnectionError:
                print(f"{Fore.RED}\n" + "="*50)
                print("Retry failed. Overwolf still not accessible. Exiting in 5 seconds!")
                print("="*50 + f"\n{Fore.RESET}")
                time.sleep(5)
                return f"{Fore.RED}Retry failed. Overwolf still not accessible.{Fore.RESET}"

        target_ws_url = next(
            (t["webSocketDebuggerUrl"] for t in targets if t["title"] == "Overwolf GameEvents Provider index"), None)

        if not target_ws_url:
            print(f"{Fore.RED}\n" + "="*50)
            print("WebSocket target not found in Overwolf tabs [Make sure Siege is open!]. Exiting in 5 seconds!")
            print("="*50 + f"\n{Fore.RESET}")
            time.sleep(5)

            return f"{Fore.RED}WebSocket target not found in Overwolf tabs.{Fore.RESET}"

        ws = websocket.create_connection(target_ws_url)
        siege_spider_api_base_url = SIEGE_SPIDER_API_BASE_URL
        siege_spider_dashboard_url = SIEGE_SPIDER_DASHBOARD_BASE_URL

        js_code = """
            (function() {{
                console.log = m => {{
                    if (m.startsWith("[PLUGIN INFO]")) {{
                        const jsonString = m.substring(m.indexOf('{{'));
                        try {{
                            const parsedMsg = JSON.parse(jsonString);
                            if (['player_list_log'].includes(parsedMsg.key)) {{
                                const players = JSON.parse(parsedMsg.value);
                                
                                const identifiers = players.map(p => ({{
                                    [p.profile_id]: p.team_id
                                }}));
                                
                                const matchData = {{
                                    identifiers: identifiers
                                }};
                                
                                fetch("{siege_spider_api_base_url}/ingest/match", {{
                                    method: "POST",
                                    headers: {{
                                        "Content-Type": "application/json"
                                    }},
                                    body: JSON.stringify(matchData)
                                }})
                                .then(apiResponse => apiResponse.json())
                                .then(responseData => {{
                                    if (responseData.id) {{
                                       overwolf.utils.openUrlInDefaultBrowser(`{siege_spider_dashboard_url}/lookup/match/${{responseData.id}}`);
                                    }}
                                }})
                                .catch(error => {{
                                    console.error('API request failed:', error);
                                }});
                            }}
                        }} catch (e) {{
                            console.error('Failed to parse JSON:', e);
                        }}
                    }}
                }};
            }})();
        """.format(
            siege_spider_api_base_url=siege_spider_api_base_url,
            siege_spider_dashboard_url=siege_spider_dashboard_url,
        )

        js_code = js_code.format(
            siege_spider_api_base_url=siege_spider_api_base_url,
            siege_spider_dashboard_url=siege_spider_dashboard_url
        )

        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": js_code, "returnByValue": False}
        }))
        ws.close()
        print(f"{Fore.GREEN}\n" + "="*50)
        print("Javascript injected successfully! Exiting in 5 seconds!")
        print("="*50 + f"\n{Fore.RESET}")
        time.sleep(5)

        return "JavaScript injected successfully."

    except (requests.RequestException, websocket.WebSocketException) as e:
        print(f"{Fore.RED}\n" + "="*50)
        print("Javascript injection failed! Exiting in 5 seconds!")
        print("="*50 + f"\n{Fore.RESET}")
        time.sleep(5)
        return f"{Fore.RED}Error: {e}{Fore.RESET}"

if __name__ == "__main__":
    print_banner()
    check_version()
    time.sleep(1)
    print("Injecting JavaScript...")

    # Now inject the javascript into overwolf
    result = inject_javascript()
