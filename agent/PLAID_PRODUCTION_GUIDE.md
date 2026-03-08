# Going Live: Connecting Real Brokerage Accounts via Plaid

This guide walks you through moving from Plaid Sandbox (fake data) to Development (real accounts). Once complete, your agent will analyze your actual Stash, Robinhood, SoFi, and Fidelity holdings.

---

## Overview

| Environment | What It Does | Cost | Limit |
|---|---|---|---|
| **Sandbox** (current) | Simulated data, fake accounts | Free | Unlimited |
| **Development** (next step) | Real accounts, real data | Free | 100 connections |
| **Production** | Full scale | Paid (starts ~$500/mo) | Unlimited |

**You want Development.** It's free, supports 100 real account connections, and is more than enough for personal use.

---

## Step-by-Step

### Step 1: Apply for Development Access

1. Go to **https://dashboard.plaid.com**
2. Log into your Plaid account
3. In the left sidebar, click **Account** → **Billing** (or look for an "Upgrade" or "Request Development" button)
4. You may see a banner or section for "Apply for Development access"
5. Fill out the application:
   - **Company name**: Your name or a personal project name
   - **Use case**: "Personal portfolio monitoring and analytics"
   - **Description**: "I'm building a personal tool to aggregate my brokerage accounts (Stash, Robinhood, SoFi, Fidelity) and analyze investment performance. For personal use only, not a commercial product."
   - **Expected volume**: 4 connections (one per brokerage)
   - **Products needed**: Investments
6. Submit and wait for approval (usually **1-3 business days**, sometimes same-day)

> ⚠️ If you can't find the Development application on the dashboard, email devs@plaid.com with the description above. Plaid's dashboard layout changes frequently.

### Step 2: Get Your Development Secret

Once approved:

1. Go to **https://dashboard.plaid.com/developers/keys**
2. You'll now see a **Development** section alongside Sandbox
3. Copy your **Development secret** (client_id stays the same)
4. Update your `.env`:

```bash
PLAID_CLIENT_ID=your_same_client_id
PLAID_SECRET=your_new_development_secret    # <-- changed
PLAID_ENV=development                        # <-- changed from "sandbox"
```

### Step 3: Update plaid_config.py

The config already supports Development — just make sure this mapping exists:

```python
PLAID_ENV_URLS = {
    "sandbox": plaid.Environment.Sandbox,
    "development": plaid.Environment.Development,  # <-- this line
    "production": plaid.Environment.Production,
}
```

Our `plaid_config.py` already has this. Just changing `.env` is enough.

### Step 4: Build the Plaid Link Flow

In Sandbox we bypassed the browser login. With real accounts, you need **Plaid Link** — a secure widget that opens your brokerage's login page. Here's a minimal approach:

#### Option A: Quick & Dirty (Local HTML file)

Create a file called `connect_real_account.py` in your project root:

```python
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
```

### Step 5: Connect Each Brokerage

1. Run the connect script:
   ```bash
   uv run python connect_real_account.py
   ```

2. Open **http://localhost:5555** in your browser

3. For each brokerage, enter the nickname and click Connect:

   | Nickname | What Happens |
   |---|---|
   | `stash` | Plaid Link opens → search "Stash" → log in with your Stash credentials |
   | `robinhood` | Plaid Link opens → search "Robinhood" → log in with Robinhood credentials |
   | `sofi` | Plaid Link opens → search "SoFi" → log in with SoFi credentials |
   | `fidelity` | Plaid Link opens → search "Fidelity" → log in with Fidelity credentials |

4. Each successful connection saves an access token to `access_tokens.json`

5. After connecting all 4, stop the server (Ctrl+C) — you won't need it again unless a token expires

### Step 6: Verify With Notebook 02

Open notebook `02_fetch_holdings.ipynb` and run it. You should now see your **real** holdings, balances, and positions across all 4 brokerages.

---

## Important Notes

### Token Persistence
- Access tokens **don't expire** — they remain valid until you or the brokerage revokes them
- If a connection breaks (e.g., you changed your brokerage password), you'll get an `ITEM_LOGIN_REQUIRED` error
- To fix: re-run `connect_real_account.py` and reconnect that brokerage with the same nickname (overwrites the old token)

### Data Freshness
- Plaid refreshes investment data **once daily**, typically overnight after market close
- The data you see is from the **previous trading day's close**
- If you need intra-day data, yfinance (notebook 03) already supplements with current prices
- Plaid offers a paid `/investments/refresh` endpoint for on-demand refresh if you ever need it

### Security Checklist
- [ ] `.env` is in `.gitignore` ✅ (already done)
- [ ] `access_tokens.json` is in `.gitignore` ✅ (already done)
- [ ] Development secret is different from Sandbox secret
- [ ] Never share your access tokens — they grant read access to your financial data
- [ ] Consider encrypting `access_tokens.json` if your machine isn't encrypted at rest

### Supported Brokerages via Plaid
Your four brokerages are all supported:

| Brokerage | Plaid Support | Search Name in Link |
|---|---|---|
| Stash | ✅ Investments | "Stash" |
| Robinhood | ✅ Investments | "Robinhood" |
| SoFi | ✅ Investments | "SoFi" or "SoFi Invest" |
| Fidelity | ✅ Investments | "Fidelity" |

### Costs
- **Development environment**: Free, up to 100 item connections
- **4 brokerages × 1 connection each**: 4 out of 100 — plenty of headroom
- **You will never need Production** for personal use

### Troubleshooting

| Issue | Fix |
|---|---|
| Can't find brokerage in Plaid Link | Try alternate names (e.g., "SoFi Invest" vs "SoFi") |
| `ITEM_LOGIN_REQUIRED` | Re-connect the account — you probably changed your password or MFA |
| `INVESTMENTS_NOT_FOUND` | The account type doesn't have investment data (e.g., a checking account) |
| `NO_ACCOUNTS` | You connected but didn't select an investment account in the Link flow |
| Empty holdings | Plaid may take up to 24 hours for the first data pull after connecting |
| `INVALID_API_KEYS` | Make sure `.env` has the **Development** secret, not Sandbox |

---

## Quick Reference

```bash
# One-time setup
uv run python connect_real_account.py   # Connect each brokerage at localhost:5555

# Daily analysis (manual)
uv run jupyter notebook                 # Run notebooks 02 → 03 → 04

# Daily analysis (automated)
uv run python run_pipeline.py           # Runs everything end-to-end

# Scheduled (cron — weekdays 7 AM)
# crontab -e, then add:
0 7 * * 1-5 cd /full/path/to/financial-agent && /full/path/to/.local/bin/uv run python run_pipeline.py >> pipeline.log 2>&1
```
