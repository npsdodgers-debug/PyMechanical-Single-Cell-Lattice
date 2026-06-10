"""
classifier.py

sklearn-based SHM classifier with Leave-One-Out cross-validation.
LOO is appropriate when sample count is small (< ~30).

Switch to StratifiedKFold (k=5) once you have ~20+ samples per class.
"""

import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import LeaveOneOut, cross_val_score, cross_val_predict
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.impute import SimpleImputer


def build_pipeline(model='rf'):
    """
    StandardScaler → Imputer (fills NaN peaks) → Classifier.

    model : 'rf'  RandomForest   — good default, handles small N well
            'svm' RBF-kernel SVM — often better with very few samples
    """
    if model == 'rf':
        clf = RandomForestClassifier(n_estimators=200, random_state=42)
    elif model == 'svm':
        clf = SVC(kernel='rbf', probability=True, random_state=42)
    else:
        raise ValueError(f"Unknown model '{model}'. Choose 'rf' or 'svm'.")

    return Pipeline([
        ('imputer', SimpleImputer(strategy='median')),  # handles NaN padded peaks
        ('scaler',  StandardScaler()),
        ('clf',     clf),
    ])


def train(X, y, model='rf'):
    """Fit on all data. Use evaluate() for honest LOO accuracy estimate."""
    pipe = build_pipeline(model)
    pipe.fit(X.values, y)
    return pipe


def evaluate(X, y, model='rf', label_names=None):
    """
    Leave-One-Out cross-validation accuracy.
    Prints classification report and confusion matrix.
    Returns fitted pipeline trained on full data.
    """
    if len(np.unique(y)) < 2:
        print("Need at least 2 classes to evaluate. Collect more samples first.")
        return None

    pipe  = build_pipeline(model)
    y_hat = cross_val_predict(pipe, X.values, y, cv=LeaveOneOut())

    classes = np.unique(y)
    if label_names is None:
        label_names = [str(c) for c in classes]

    print(f"\n── LOO Classification Report ({model.upper()}) ──")
    print(classification_report(y, y_hat, labels=classes, target_names=label_names))
    print("Confusion matrix (rows=true, cols=predicted):")
    print(confusion_matrix(y, y_hat, labels=classes))

    # Refit on full dataset
    pipe.fit(X.values, y)
    return pipe


def predict(pipe, X_row):
    """
    Predict a single sample.

    X_row : dict of feature_name→value, or 1-row pd.DataFrame
    Returns (label_int, probabilities_array)
    """
    import pandas as pd
    if isinstance(X_row, dict):
        X_row = pd.DataFrame([X_row])
    label = pipe.predict(X_row.values)[0]
    proba = pipe.predict_proba(X_row.values)[0]
    return int(label), proba


def save_model(pipe, path):
    joblib.dump(pipe, path)
    print(f"Model saved: {path}")


def load_model(path):
    return joblib.load(path)
