"""
Fyers login (OAuth). Fyers access tokens expire every day, so this runs once per day:

  1. login_url()           -> the Fyers login page for your app
  2. you log in on Fyers   -> Fyers redirects to FYERS_REDIRECT_URI?auth_code=...
  3. exchange_auth_code()  -> swaps that one-time code for an access token
                              and saves it to .env as FYERS_ACCESS_TOKEN
"""
import os
from dotenv import set_key
from fyers_apiv3 import fyersModel

import config
from app.services.fyers_service import FyersError

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")


def make_session():
    if not config.FYERS_CLIENT_ID or config.FYERS_CLIENT_ID.startswith("your_") or not config.FYERS_SECRET_KEY:
        raise FyersError("Set FYERS_CLIENT_ID and FYERS_SECRET_KEY in .env first (from myapi.fyers.in)")
    return fyersModel.SessionModel(
        client_id=config.FYERS_CLIENT_ID,
        secret_key=config.FYERS_SECRET_KEY,
        redirect_uri=config.FYERS_REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code",
        state="trading-ai",
    )


def login_url():
    return make_session().generate_authcode()


def exchange_auth_code(auth_code):
    session = make_session()
    session.set_token(auth_code)
    response = session.generate_token()
    if response.get("s") != "ok" or "access_token" not in response:
        raise FyersError(response.get("message", "Fyers did not return an access token"))

    token = response["access_token"]
    set_key(ENV_PATH, "FYERS_ACCESS_TOKEN", token)   # remembered after restarts
    config.FYERS_ACCESS_TOKEN = token                # used straight away
    return token
