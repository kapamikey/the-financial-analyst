"""
Spin up a temporary local server to run Plaid Link.
Usage: uv run python connect_real_account.py
Then open http://localhost:5555 in your browser.
"""

import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs

from dotenv import load_dotenv

load_dotenv()

# We need these for the inline server
from plaid_config import get_plaid_client, PLAID_ENV
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

client = get_plaid_client()
TOKENS_FILE = "access_tokens.json"


def load_tokens():
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE) as f:
            return json.load(f)
    return {}


def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._serve_page()
        elif self.path == "/create_link_token":
            self._create_link_token()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/exchange":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            self._exchange_token(body)
        else:
            self.send_error(404)

    def _create_link_token(self):
        request = LinkTokenCreateRequest(
            products=[Products("investments")],
            client_name="Financial Analyst Agent",
            country_codes=[CountryCode("US")],
            language="en",
            user=LinkTokenCreateRequestUser(client_user_id="user-1"),
        )
        response = client.link_token_create(request)
        self._json_response({"link_token": response.link_token})

    def _exchange_token(self, body):
        public_token = body.get("public_token")
        nickname = body.get("nickname", "unknown")

        exchange_req = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_resp = client.item_public_token_exchange(exchange_req)

        tokens = load_tokens()
        tokens[nickname] = exchange_resp.access_token
        save_tokens(tokens)

        self._json_response({
            "status": "ok",
            "nickname": nickname,
            "item_id": exchange_resp.item_id,
        })

    def _serve_page(self):
        tokens = load_tokens()
        connected_list = ", ".join(tokens.keys()) if tokens else "None yet"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Connect Brokerage</title>
    <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
    <style>
        body {{ font-family: system-ui; max-width: 600px; margin: 40px auto; background: #1a1a2e; color: #e0e0e0; padding: 20px; }}
        h1 {{ color: #fff; }}
        input, button {{ padding: 10px 16px; font-size: 16px; border-radius: 6px; border: 1px solid #444; background: #16213e; color: #fff; }}
        button {{ cursor: pointer; background: #2563eb; border-color: #2563eb; }}
        button:hover {{ background: #1d4ed8; }}
        #status {{ margin-top: 20px; padding: 12px; border-radius: 6px; background: #16213e; }}
    </style>
</head>
<body>
    <h1>🔗 Connect Brokerage Account</h1>
    <p>Connected: <strong>{connected_list}</strong></p>
    <p>Environment: <strong>{PLAID_ENV}</strong></p>
    <hr>
    <label>Nickname for this account:</label><br>
    <input type="text" id="nickname" placeholder="e.g. stash, robinhood, sofi, fidelity" style="width: 300px; margin: 8px 0;">
    <br><br>
    <button onclick="startLink()">Connect Account via Plaid</button>
    <div id="status"></div>
    <script>
        async function startLink() {{
            const nickname = document.getElementById('nickname').value.trim();
            if (!nickname) {{ alert('Enter a nickname first'); return; }}

            document.getElementById('status').innerHTML = 'Starting Plaid Link...';

            const resp = await fetch('/create_link_token');
            const {{ link_token }} = await resp.json();

            const handler = Plaid.create({{
                token: link_token,
                onSuccess: async (public_token, metadata) => {{
                    document.getElementById('status').innerHTML = 'Exchanging token...';
                    const exResp = await fetch('/exchange', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ public_token, nickname }}),
                    }});
                    const result = await exResp.json();
                    document.getElementById('status').innerHTML =
                        '✅ Connected <strong>' + nickname + '</strong> (item: ' + result.item_id + ')<br>Reload to connect another.';
                }},
                onExit: (err) => {{
                    if (err) document.getElementById('status').innerHTML = '❌ ' + err.display_message;
                }},
            }});
            handler.open();
        }}
    </script>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def _json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f"  [{self.address_string()}] {format % args}")


if __name__ == "__main__":
    port = 5555
    print(f"\\n🔗 Plaid Link Server ({PLAID_ENV} mode)")
    print(f"   Open http://localhost:{port} in your browser")
    print(f"   Press Ctrl+C to stop\\n")
    HTTPServer(("", port), Handler).serve_forever()
