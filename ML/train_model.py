"""
Train + evaluate the Symptom -> Specialization model (Logistic Regression).

Pipeline: text cleaning -> TF-IDF (1-2 grams) -> Logistic Regression.
Outputs: symptom_model.joblib, metrics.json, confusion_matrix.png
Run:  python train_model.py
"""
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer
from text_utils import clean_text

RANDOM_STATE = 42


def build_pipeline():
    return Pipeline([
        ("clean", FunctionTransformer(clean_text, validate=False)),
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=2000, C=5.0)),
    ])


def main():
    df = pd.read_csv("symptom_dataset.csv").dropna()
    X_train, X_test, y_train, y_test = train_test_split(
        df.symptoms, df.specialization, test_size=0.2, stratify=df.specialization, random_state=RANDOM_STATE)

    model = build_pipeline().fit(X_train, y_train)
    pred = model.predict(X_test)

    acc = accuracy_score(y_test, pred)
    f1 = f1_score(y_test, pred, average="macro")
    cv = cross_val_score(build_pipeline(), df.symptoms, df.specialization, cv=5)
    print(f"Test accuracy : {acc:.4f}\nMacro F1      : {f1:.4f}\n5-fold CV acc : {cv.mean():.4f} +/- {cv.std():.4f}\n")
    print(classification_report(y_test, pred))

    labels = sorted(df.specialization.unique())
    cm = confusion_matrix(y_test, pred, labels=labels)
    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=60, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=7, color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual"); ax.set_title("Confusion Matrix - Test Set")
    fig.colorbar(im); fig.tight_layout(); fig.savefig("confusion_matrix.png", dpi=120)

    # final model: retrain on ALL data for deployment
    final = build_pipeline().fit(df.symptoms, df.specialization)
    joblib.dump(final, "symptom_model.joblib")
    json.dump({"test_accuracy": round(acc, 4), "macro_f1": round(f1, 4), "cv_mean": round(float(cv.mean()), 4),
               "cv_std": round(float(cv.std()), 4), "n_samples": int(len(df)), "classes": labels},
              open("metrics.json", "w"), indent=2)
    print("Saved symptom_model.joblib, metrics.json, confusion_matrix.png")


if __name__ == "__main__":
    main()
