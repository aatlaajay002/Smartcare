"""Machine Learning service: loads the saved Logistic Regression model and predicts specialization."""
import sys
import joblib
from config import Config

sys.path.insert(0, str(Config.ML_DIR))        # lets joblib find ML/text_utils.clean_text

_model = None


def _get_model():
    global _model
    if _model is None:
        if not Config.MODEL_PATH.exists():
            raise FileNotFoundError("Model not found. Run:  cd ML && python train_model.py")
        _model = joblib.load(Config.MODEL_PATH)
    return _model


def predict_specializations(symptoms: str, top_k: int = 3):
    """Return top-k [{specialization, probability}] sorted by confidence."""
    model = _get_model()
    probs = model.predict_proba([symptoms])[0]
    classes = model.classes_
    ranked = sorted(zip(classes, probs), key=lambda x: x[1], reverse=True)[:top_k]
    return [{"specialization": c, "probability": round(float(p), 4)} for c, p in ranked]
