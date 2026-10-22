"""
Get today's Fyers access token from the command line.

Easiest way: start the server and click "Connect Fyers" on the dashboard.
Use this script if the server isn't running:

    python auth.py

It opens the Fyers login page. After you log in, your browser goes to your
redirect URL (the page may fail to load - that's fine). Copy the FULL address
from the browser's address bar and paste it here. The token is saved to .env.
"""
import webbrowser
from urllib.parse import parse_qs, urlparse

from app.services.fyers_auth import exchange_auth_code, login_url

url = login_url()
print("\n1. Log in to Fyers here (opening your browser):\n\n   " + url + "\n")
webbrowser.open(url)

pasted = input("2. Paste the full URL you were sent to after logging in:\n> ").strip()
auth_code = parse_qs(urlparse(pasted).query).get("auth_code", [pasted])[0]

exchange_auth_code(auth_code)
print("\nDone! FYERS_ACCESS_TOKEN saved to .env. Restart the server to use live data.")
