"""
Advanced models, all usable like normal scikit-learn models (fit / predict_proba):

  LSTMClassifier      - PyTorch neural network that reads the LAST 30 CANDLES as a
                        sequence, instead of looking at one candle at a time.
  EnsembleClassifier  - averages the probabilities of several models ("soft voting").
                        Different models make different mistakes, so the average
                        is often steadier than any single one.
  tune_lightgbm()     - LightGBM (fast gradient boosting) with its settings chosen
                        automatically by Optuna, which tries many combinations and
                        learns which areas of the search space work best.
"""
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    TORCH_AVAILABLE = True
except ImportError:          # the app still works without PyTorch, just without the LSTM
    TORCH_AVAILABLE = False


# ======================================================================
# LSTM (Long Short-Term Memory) neural network
# ======================================================================
if TORCH_AVAILABLE:
    class _LSTMNet(nn.Module):
        def __init__(self, n_features, hidden):
            super().__init__()
            self.lstm = nn.LSTM(n_features, hidden, batch_first=True)
            self.dropout = nn.Dropout(0.2)          # randomly switch off neurons -> less overfitting
            self.head = nn.Linear(hidden, 1)

        def forward(self, x):                       # x: (batch, window, features)
            out, _ = self.lstm(x)
            last = out[:, -1, :]                    # the network's "memory" after reading the whole window
            return self.head(self.dropout(last)).squeeze(-1)


class LSTMClassifier(BaseEstimator, ClassifierMixin):
    def __init__(self, window=30, hidden=32, epochs=15, lr=0.003, batch_size=64, random_state=42):
        self.window = window
        self.hidden = hidden
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.random_state = random_state

    def _sequences(self, X):
        """Turn rows into overlapping windows: row i -> rows (i-window+1 ... i).
        The first rows have no full history, so we pad by repeating the first row."""
        Xs = self.scaler_.transform(np.asarray(X, dtype=np.float32)).astype(np.float32)
        padded = np.vstack([np.repeat(Xs[:1], self.window - 1, axis=0), Xs])
        idx = np.arange(len(Xs))[:, None] + np.arange(self.window)[None, :]
        return torch.from_numpy(padded[idx])        # (rows, window, features)

    def fit(self, X, y):
        torch.manual_seed(self.random_state)
        rng = np.random.default_rng(self.random_state)
        self.classes_ = np.array([0, 1])
        self.scaler_ = StandardScaler().fit(np.asarray(X, dtype=np.float32))   # neural nets need scaled inputs

        seqs = self._sequences(X)
        target = torch.tensor(np.asarray(y), dtype=torch.float32)

        self.net_ = _LSTMNet(seqs.shape[2], self.hidden)
        optimizer = torch.optim.Adam(self.net_.parameters(), lr=self.lr, weight_decay=1e-4)
        loss_fn = nn.BCEWithLogitsLoss()

        self.net_.train()
        for _ in range(self.epochs):
            # Each window only contains its own past, so shuffling windows is safe
            order = rng.permutation(len(seqs))
            for start in range(0, len(order), self.batch_size):
                batch = order[start:start + self.batch_size]
                optimizer.zero_grad()
                loss = loss_fn(self.net_(seqs[batch]), target[batch])
                loss.backward()
                optimizer.step()
        return self

    def predict_proba(self, X):
        self.net_.eval()
        with torch.no_grad():
            p = torch.sigmoid(self.net_(self._sequences(X))).numpy()
        return np.column_stack([1 - p, p])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] > 0.5).astype(int)


# ======================================================================
# Ensemble (soft voting)
# ======================================================================
class EnsembleClassifier(BaseEstimator, ClassifierMixin):
    def __init__(self, members=None):
        self.members = members

    def fit(self, X, y):
        self.classes_ = np.array([0, 1])
        self.fitted_ = [clone(m).fit(X, y) for m in self.members]
        return self

    def predict_proba(self, X):
        return np.mean([m.predict_proba(X) for m in self.fitted_], axis=0)

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] > 0.5).astype(int)


# ======================================================================
# LightGBM + Optuna hyper-parameter tuning
# ======================================================================
def tune_lightgbm(X, y, n_trials=25, n_splits=3):
    """Search for the best LightGBM settings using walk-forward AUC as the score.
    Only ever called on the development data, never on the holdout."""
    import optuna
    from lightgbm import LGBMClassifier

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    folds = list(TimeSeriesSplit(n_splits=n_splits, gap=1).split(X))

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 400),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 8, 48),
            "min_child_samples": trial.suggest_int("min_child_samples", 20, 120),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10, log=True),
        }
        model = LGBMClassifier(**params, subsample_freq=1, random_state=42, verbose=-1)
        aucs = []
        for train_idx, test_idx in folds:
            model.fit(X.iloc[train_idx], y.iloc[train_idx])
            aucs.append(roc_auc_score(y.iloc[test_idx], model.predict_proba(X.iloc[test_idx])[:, 1]))
        return float(np.mean(aucs))

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials)

    best = LGBMClassifier(**study.best_params, subsample_freq=1, random_state=42, verbose=-1)
    tuning = {
        "trials": n_trials,
        "best_auc": round(study.best_value, 4),
        "params": {k: round(v, 4) if isinstance(v, float) else v for k, v in study.best_params.items()},
    }
    return best, tuning
