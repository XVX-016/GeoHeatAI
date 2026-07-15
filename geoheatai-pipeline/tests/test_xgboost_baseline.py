import numpy as np

from src.ml import xgboost_baseline as xb


def test_train_stacked_ensemble_returns_predictions_and_models():
    rng = np.random.default_rng(42)
    X = rng.normal(size=(40, 4))
    y = 1.5 + 0.8 * X[:, 0] - 0.4 * X[:, 1] + rng.normal(scale=0.05, size=40)

    preds, final_xgb, final_lgb, meta = xb.train_stacked_ensemble(X, y, X)

    assert preds.shape == (40,)
    assert final_xgb is not None
    assert final_lgb is not None
    assert meta is not None
