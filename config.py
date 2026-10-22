from dotenv import load_dotenv
import os

load_dotenv()

# ---- Fyers credentials (from .env) ----
FYERS_CLIENT_ID = os.getenv("FYERS_CLIENT_ID")
FYERS_SECRET_KEY = os.getenv("FYERS_SECRET_KEY")
FYERS_REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN")

# ---- Data ----
HISTORY_DAYS = 60            # how many days of 5-minute candles to fetch (Fyers allows up to 100)
CACHE_SECONDS = 60           # reuse fetched data for this long instead of calling Fyers again

# ---- Strategy / backtest ----
AI_BUY_THRESHOLD = 0.55      # AI goes long when P(up) is above this
AI_SELL_THRESHOLD = 0.45     # AI goes short when P(up) is below this
TRADING_COST = 0.0003        # 0.03% per position change (brokerage + taxes, approx.)
CANDLES_PER_YEAR = 75 * 252  # 75 five-minute candles a day, 252 trading days

# ---- Model training ----
OPTUNA_TRIALS = 25           # how many LightGBM settings Optuna tries
