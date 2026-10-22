import os

from app.models import train_model as tm
from app.services import model_service
from app.services.data_service import add_features, convert_to_dataframe
from app.services.demo_service import generate_demo_response


def test_train_and_predict_end_to_end(tmp_path, monkeypatch):
    # Save the model into a temp folder instead of the real one
    monkeypatch.setattr(tm, "MODELS_DIR", str(tmp_path))
    monkeypatch.setattr(tm, "OPTUNA_TRIALS", 3)     # keep the test fast
    symbol = "NSE:TEST-EQ"
    df = add_features(convert_to_dataframe(generate_demo_response(symbol, n=900)))

    metrics = tm.train_model(df, symbol)

    assert os.path.exists(tm.model_path(symbol))
    names = [r["name"] for r in metrics["comparison"]]
    assert metrics["best_model"] in names and tm.ENSEMBLE in names
    assert sum(r["best"] for r in metrics["comparison"]) == 1
    assert 0 <= metrics["test_accuracy"] <= 1
    c = metrics["confusion"]
    assert c["tn"] + c["fp"] + c["fn"] + c["tp"] == metrics["test_rows"]

    info = model_service.get_model_info(symbol)
    assert set(info["backtest"]["stats"]) == {"ai", "rules", "buy_hold"}
    assert len(info["backtest"]["equity"]) == metrics["test_rows"]

    pred = model_service.predict_latest(df, symbol)
    assert pred["action"] in {"BUY", "SELL", "HOLD"}
    assert 0 <= pred["probability_up"] <= 1


def test_untrained_symbol_has_no_model(tmp_path, monkeypatch):
    monkeypatch.setattr(tm, "MODELS_DIR", str(tmp_path))
    assert model_service.get_model_info("NSE:NOPE-EQ") is None
