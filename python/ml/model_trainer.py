#!/usr/bin/env python3
"""
model_trainer.py
Satellite Ground Station - ML Model Training

Trains classification and regression models on historical mission data.

Models:
    - Success Classifier: RandomForest predicting decode_success
    - SNR Regressor: RandomForest predicting snr_db

Training pipeline:
    1. Load historical data from data_store
    2. Extract features via feature_engineering
    3. Split train/test
    4. Train models with cross-validation
    5. Evaluate and save best model

Author: Luke Waszyn
Date: February 2026
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from python.data_store import get_training_data, get_missions
from python.ml.feature_engineering import (
    features_to_dataframe,
    get_feature_names,
    impute_missing,
    extract_all_features
)

# Model configuration
MODEL_DIR = Path('data/ml/models')
CLASSIFIER_PATH = MODEL_DIR / 'success_classifier.joblib'
REGRESSOR_PATH = MODEL_DIR / 'snr_regressor.joblib'
METADATA_PATH = MODEL_DIR / 'model_metadata.json'

# Training parameters
MIN_SAMPLES = 20            # Minimum samples to train
TEST_SIZE = 0.2             # 20% for testing
RANDOM_STATE = 42           # Reproducibility
CV_FOLDS = 5                # Cross-validation folds

# Model hyperparameters
CLASSIFIER_PARAMS = {
    'n_estimators': 100,
    'max_depth': 10,
    'min_samples_split': 5,
    'min_samples_leaf': 2,
    'random_state': RANDOM_STATE,
}

REGRESSOR_PARAMS = {
    'n_estimators': 100,
    'max_depth': 10,
    'min_samples_split': 5,
    'min_samples_leaf': 2,
    'random_state': RANDOM_STATE,
}


def load_training_data() -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Load and prepare training data.
    
    Returns:
        Tuple of (X, y_class, y_reg)
        - X: Feature DataFrame
        - y_class: Binary classification target (decode_success)
        - y_reg: Regression target (snr_db, may have NaN)
    """
    # Get training samples
    samples = get_training_data()
    
    if not samples:
        raise ValueError("No training data available")
    
    print(f"Loaded {len(samples)} training samples")
    
    # Convert to DataFrames
    features_list = []
    labels_list = []
    
    for sample in samples:
        features_list.append(sample['features'])
        labels_list.append(sample['labels'])
    
    X = pd.DataFrame(features_list)
    y_df = pd.DataFrame(labels_list)
    
    # Handle categorical features
    if 'antenna_type' in X.columns:
        X = pd.get_dummies(X, columns=['antenna_type'], prefix='antenna')
    
    if 'satellite' in X.columns:
        X = pd.get_dummies(X, columns=['satellite'], prefix='sat')
    
    # Impute missing values
    X = impute_missing(X)
    
    # Extract targets
    y_class = y_df['decode_success'].astype(int)
    y_reg = y_df['snr_db']  # May contain NaN
    
    return X, y_class, y_reg


def train_classifier(X: pd.DataFrame, y: pd.Series) -> Tuple[Any, Dict]:
    """
    Train success classifier.
    
    Args:
        X: Feature matrix
        y: Binary target (decode_success)
    
    Returns:
        Tuple of (model, metrics)
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, 
        f1_score, roc_auc_score, confusion_matrix
    )
    
    print("\nTraining success classifier...")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    
    print(f"  Train size: {len(X_train)}, Test size: {len(X_test)}")
    print(f"  Positive rate: {y.mean():.1%}")
    
    # Train model
    model = RandomForestClassifier(**CLASSIFIER_PARAMS)
    model.fit(X_train, y_train)
    
    # Cross-validation
    cv_scores = cross_val_score(model, X, y, cv=min(CV_FOLDS, len(y) // 2), scoring='accuracy')
    
    # Test set evaluation
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else y_pred
    
    metrics = {
        'accuracy': float(accuracy_score(y_test, y_pred)),
        'precision': float(precision_score(y_test, y_pred, zero_division=0)),
        'recall': float(recall_score(y_test, y_pred, zero_division=0)),
        'f1': float(f1_score(y_test, y_pred, zero_division=0)),
        'cv_mean': float(cv_scores.mean()),
        'cv_std': float(cv_scores.std()),
        'test_size': len(X_test),
        'train_size': len(X_train),
    }
    
    # ROC AUC if we have both classes
    if len(np.unique(y_test)) > 1:
        metrics['roc_auc'] = float(roc_auc_score(y_test, y_proba))
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    metrics['confusion_matrix'] = cm.tolist()
    
    # Feature importance
    importance = dict(zip(X.columns, model.feature_importances_))
    metrics['feature_importance'] = {k: float(v) for k, v in 
                                      sorted(importance.items(), key=lambda x: -x[1])[:10]}
    
    print(f"  Accuracy: {metrics['accuracy']:.1%}")
    print(f"  Precision: {metrics['precision']:.1%}")
    print(f"  Recall: {metrics['recall']:.1%}")
    print(f"  F1: {metrics['f1']:.3f}")
    print(f"  CV Score: {metrics['cv_mean']:.1%} ± {metrics['cv_std']:.1%}")
    
    return model, metrics


def train_regressor(X: pd.DataFrame, y: pd.Series) -> Tuple[Optional[Any], Dict]:
    """
    Train SNR regressor.
    
    Args:
        X: Feature matrix
        y: Continuous target (snr_db)
    
    Returns:
        Tuple of (model, metrics) or (None, {}) if insufficient data
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    
    # Filter to samples with valid SNR
    valid_mask = y.notna()
    X_valid = X[valid_mask]
    y_valid = y[valid_mask]
    
    if len(y_valid) < MIN_SAMPLES // 2:
        print(f"\nSkipping regressor: only {len(y_valid)} samples with SNR data")
        return None, {}
    
    print(f"\nTraining SNR regressor ({len(y_valid)} samples with SNR data)...")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X_valid, y_valid, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )
    
    # Train model
    model = RandomForestRegressor(**REGRESSOR_PARAMS)
    model.fit(X_train, y_train)
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_valid, y_valid, 
                                 cv=min(CV_FOLDS, len(y_valid) // 2), 
                                 scoring='neg_mean_squared_error')
    
    # Test set evaluation
    y_pred = model.predict(X_test)
    
    metrics = {
        'mse': float(mean_squared_error(y_test, y_pred)),
        'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred))),
        'mae': float(mean_absolute_error(y_test, y_pred)),
        'r2': float(r2_score(y_test, y_pred)),
        'cv_rmse_mean': float(np.sqrt(-cv_scores.mean())),
        'cv_rmse_std': float(np.sqrt(cv_scores.std())),
        'samples': len(y_valid),
    }
    
    # Feature importance
    importance = dict(zip(X.columns, model.feature_importances_))
    metrics['feature_importance'] = {k: float(v) for k, v in 
                                      sorted(importance.items(), key=lambda x: -x[1])[:10]}
    
    print(f"  RMSE: {metrics['rmse']:.2f} dB")
    print(f"  MAE: {metrics['mae']:.2f} dB")
    print(f"  R²: {metrics['r2']:.3f}")
    
    return model, metrics


def save_models(classifier, regressor, classifier_metrics, regressor_metrics, feature_names):
    """Save trained models and metadata."""
    import joblib
    
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save classifier
    if classifier is not None:
        joblib.dump(classifier, CLASSIFIER_PATH)
        print(f"\nSaved classifier: {CLASSIFIER_PATH}")
    
    # Save regressor
    if regressor is not None:
        joblib.dump(regressor, REGRESSOR_PATH)
        print(f"Saved regressor: {REGRESSOR_PATH}")
    
    # Save metadata
    metadata = {
        'version': datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
        'trained_at': datetime.utcnow().isoformat(),
        'training_samples': classifier_metrics.get('train_size', 0) + classifier_metrics.get('test_size', 0),
        'feature_names': list(feature_names),
        'classifier_metrics': classifier_metrics,
        'regressor_metrics': regressor_metrics,
        'parameters': {
            'classifier': CLASSIFIER_PARAMS,
            'regressor': REGRESSOR_PARAMS,
        }
    }
    
    with open(METADATA_PATH, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Saved metadata: {METADATA_PATH}")
    
    return metadata


def train_models(force: bool = False) -> Dict:
    """
    Main training function.
    
    Args:
        force: Train even with few samples (for testing)
    
    Returns:
        Training metadata
    """
    print("=" * 50)
    print("ML Model Training")
    print("=" * 50)
    
    # Load data
    try:
        X, y_class, y_reg = load_training_data()
    except ValueError as e:
        print(f"Error: {e}")
        return {}
    
    # Check minimum samples
    if len(X) < MIN_SAMPLES and not force:
        print(f"\nInsufficient data: {len(X)} samples (need {MIN_SAMPLES})")
        print("Collect more mission data before training.")
        print("Use --force to train anyway (not recommended).")
        return {}
    
    print(f"\nFeatures: {X.shape[1]}")
    print(f"Samples: {X.shape[0]}")
    
    # Train classifier
    classifier, classifier_metrics = train_classifier(X, y_class)
    
    # Train regressor
    regressor, regressor_metrics = train_regressor(X, y_reg)
    
    # Save models
    metadata = save_models(
        classifier, regressor,
        classifier_metrics, regressor_metrics,
        X.columns.tolist()
    )
    
    print("\n" + "=" * 50)
    print("Training complete!")
    print("=" * 50)
    
    return metadata


def evaluate_model() -> Dict:
    """
    Evaluate current model on all available data.
    
    Returns performance metrics.
    """
    import joblib
    from sklearn.metrics import accuracy_score, classification_report
    
    if not CLASSIFIER_PATH.exists():
        print("No trained model found")
        return {}
    
    # Load model
    classifier = joblib.load(CLASSIFIER_PATH)
    
    with open(METADATA_PATH, 'r') as f:
        metadata = json.load(f)
    
    # Load all data
    X, y_class, _ = load_training_data()
    
    # Ensure columns match
    for col in metadata['feature_names']:
        if col not in X.columns:
            X[col] = 0
    X = X[metadata['feature_names']]
    
    # Predict
    y_pred = classifier.predict(X)
    
    print("\nModel Evaluation (all data)")
    print("=" * 50)
    print(f"Accuracy: {accuracy_score(y_class, y_pred):.1%}")
    print("\nClassification Report:")
    print(classification_report(y_class, y_pred))
    
    return {
        'accuracy': float(accuracy_score(y_class, y_pred)),
        'predictions': y_pred.tolist(),
        'actuals': y_class.tolist(),
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Train ML models for mission prediction')
    parser.add_argument('command', nargs='?', default='train',
                        choices=['train', 'evaluate', 'status'],
                        help='Command to run')
    parser.add_argument('--force', action='store_true',
                        help='Train even with few samples')
    
    args = parser.parse_args()
    
    if args.command == 'train':
        train_models(force=args.force)
    elif args.command == 'evaluate':
        evaluate_model()
    elif args.command == 'status':
        print("Model Status")
        print("=" * 50)
        print(f"Classifier exists: {CLASSIFIER_PATH.exists()}")
        print(f"Regressor exists: {REGRESSOR_PATH.exists()}")
        print(f"Metadata exists: {METADATA_PATH.exists()}")
        
        if METADATA_PATH.exists():
            with open(METADATA_PATH, 'r') as f:
                meta = json.load(f)
            print(f"\nLast trained: {meta.get('trained_at', 'unknown')}")
            print(f"Training samples: {meta.get('training_samples', 'unknown')}")
            print(f"Classifier accuracy: {meta.get('classifier_metrics', {}).get('accuracy', 'N/A'):.1%}"
                  if meta.get('classifier_metrics', {}).get('accuracy') else "")
