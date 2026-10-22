"""
Checks the whole pipeline WITHOUT Fyers, using fake (random) prices.

Run:   python test_model.py

Each step prints what it produced, so you can see the data flow:
fake candles -> DataFrame -> features -> rule signal -> AI train -> AI predict
"""
from app.services.data_service import convert_to_dataframe, add_features
from app.services.strategy_service import generate_signal
from app.models.train_model import train_model
from app.services.model_service import predict_latest
from app.services.demo_service import generate_demo_response


print("STEP 1: fake Fyers response")
raw = generate_demo_response()  # same shape as a Fyers response
print(f"  {len(raw['candles'])} candles, first one: {raw['candles'][0]}\n")

print("STEP 2: convert to DataFrame")
df = convert_to_dataframe(raw)
print(df.head(3), "\n")

print("STEP 3: add features")
df = add_features(df)
print(df[["close", "returns", "ma_10", "ma_20", "volatility", "momentum"]].tail(3), "\n")

print("STEP 4: rule-based signal (1=BUY, -1=SELL, 0=HOLD)")
signals = generate_signal(df.copy())
print(signals["signal"].value_counts().to_string(), "\n")

print("STEP 5: train AI model")
print(" ", train_model(df), "\n")

print("STEP 6: AI prediction for the next candle")
print(" ", predict_latest(df, "NSE:RELIANCE-EQ"))
