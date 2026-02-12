#!/usr/bin/env python3
"""
ml_predictor.py
Satellite Ground Station - ML Model Predictor

Loads trained ML models and predicts mission success probability.

Prediction targets:
    - decode_success: Binary classification (will decode succeed?)
    - snr_db: Regression (expected signal quality)

Falls back to rule-based scoring if no trained model available.

Author: Luke Waszyn
Date: February 2026
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.ml.feature_engineering import (
    extract_all_features,
    features_to_dataframe,
    get_feature_names,
    impute_missing
)
from python.ml.pass_scorer import score_pass

# Model paths
MODEL_DIR = Path('data/ml/models')
CLASSIFIER_PATH = MODEL_DIR / 'success_classifier.joblib'
REGRESSOR_PATH = MODEL_DIR / 'snr_regressor.joblib'
METADATA_PATH = MODEL_DIR / 'model_metadata.json'


class MissionPredictor:
    """
    Predicts mission success using trained ML models.
    Falls back to rule-based scoring if models unavailable.
    """
    
    def __init__(self):
        self.classifier = None
        self.regressor = None
        self.metadata = None
        self.feature_names = None
        self.using_ml = False
        
        self._load_models()
    
    def _load_models(self):
        """Load trained models if available."""
        try:
            import joblib
            
            if CLASSIFIER_PATH.exists():
                self.classifier = joblib.load(CLASSIFIER_PATH)
                self.using_ml = True
                print(f"Loaded classifier: {CLASSIFIER_PATH}")
            
            if REGRESSOR_PATH.exists():
                self.regressor = joblib.load(REGRESSOR_PATH)
                print(f"Loaded regressor: {REGRESSOR_PATH}")
            
            if METADATA_PATH.exists():
                with open(METADATA_PATH, 'r') as f:
                    self.metadata = json.load(f)
                self.feature_names = self.metadata.get('feature_names', [])
                print(f"Model trained on {self.metadata.get('training_samples', '?')} samples")
            
        except ImportError:
            print("Warning: joblib not installed, using rule-based scoring")
            self.using_ml = False
        except Exception as e:
            print(f"Warning: Could not load models: {e}")
            self.using_ml = False
    
    def predict(self,
                pass_info: Dict,
                weather: Optional[Dict] = None,
                config: Optional[Dict] = None) -> Dict:
        """
        Predict mission outcome.
        
        Args:
            pass_info: Pass data from scheduler
            weather: Weather data (optional)
            config: Hardware config (optional)
        
        Returns:
            Dictionary with predictions:
                - success_probability: 0.0 to 1.0
                - predicted_snr_db: Expected SNR (if regressor available)
                - confidence: Confidence level
                - method: 'ml' or 'rule_based'
                - recommendation: 'capture', 'skip', or 'marginal'
        """
        # Extract features
        features = extract_all_features(pass_info, weather, config)
        
        if self.using_ml and self.classifier is not None:
            return self._predict_ml(features)
        else:
            return self._predict_rules(pass_info, weather)
    
    def _predict_ml(self, features: Dict) -> Dict:
        """Make prediction using ML model."""
        import pandas as pd
        import numpy as np
        
        # Convert to DataFrame
        df = features_to_dataframe([features])
        df = impute_missing(df)
        
        # Ensure columns match training
        if self.feature_names:
            # Add missing columns
            for col in self.feature_names:
                if col not in df.columns:
                    df[col] = 0
            # Select only training columns
            df = df[self.feature_names]
        
        # Predict probability
        if hasattr(self.classifier, 'predict_proba'):
            proba = self.classifier.predict_proba(df)[0]
            success_prob = proba[1] if len(proba) > 1 else proba[0]
        else:
            pred = self.classifier.predict(df)[0]
            success_prob = float(pred)
        
        # Predict SNR if regressor available
        predicted_snr = None
        if self.regressor is not None:
            try:
                predicted_snr = float(self.regressor.predict(df)[0])
            except:
                pass
        
        # Confidence based on probability distance from 0.5
        confidence = abs(success_prob - 0.5) * 2
        
        # Recommendation
        if success_prob >= 0.7:
            recommendation = 'capture'
        elif success_prob >= 0.4:
            recommendation = 'marginal'
        else:
            recommendation = 'skip'
        
        return {
            'success_probability': float(success_prob),
            'predicted_snr_db': predicted_snr,
            'confidence': float(confidence),
            'method': 'ml',
            'recommendation': recommendation,
            'model_version': self.metadata.get('version', 'unknown') if self.metadata else 'unknown',
        }
    
    def _predict_rules(self, pass_info: Dict, weather: Optional[Dict]) -> Dict:
        """Fall back to rule-based scoring."""
        score, breakdown = score_pass(pass_info, weather)
        
        # Map score to probability-like value
        success_prob = score
        
        # Confidence is lower for rule-based
        confidence = 0.5
        
        # Recommendation
        if success_prob >= 0.6:
            recommendation = 'capture'
        elif success_prob >= 0.35:
            recommendation = 'marginal'
        else:
            recommendation = 'skip'
        
        return {
            'success_probability': float(success_prob),
            'predicted_snr_db': None,
            'confidence': float(confidence),
            'method': 'rule_based',
            'recommendation': recommendation,
            'score_breakdown': breakdown,
        }
    
    def predict_batch(self,
                      passes: List[Dict],
                      weather: Optional[Dict] = None,
                      config: Optional[Dict] = None) -> List[Dict]:
        """
        Predict outcomes for multiple passes.
        
        Returns list of predictions in same order as input.
        """
        predictions = []
        for p in passes:
            pred = self.predict(p, weather, config)
            pred['pass_info'] = p
            predictions.append(pred)
        return predictions
    
    def rank_passes(self,
                    passes: List[Dict],
                    weather: Optional[Dict] = None,
                    config: Optional[Dict] = None) -> List[Dict]:
        """
        Rank passes by predicted success probability.
        
        Returns predictions sorted by success_probability descending.
        """
        predictions = self.predict_batch(passes, weather, config)
        predictions.sort(key=lambda x: x['success_probability'], reverse=True)
        return predictions
    
    def get_status(self) -> Dict:
        """Get predictor status."""
        return {
            'using_ml': self.using_ml,
            'classifier_loaded': self.classifier is not None,
            'regressor_loaded': self.regressor is not None,
            'model_metadata': self.metadata,
            'feature_count': len(self.feature_names) if self.feature_names else 0,
        }


# Global predictor instance
_predictor = None


def get_predictor() -> MissionPredictor:
    """Get or create global predictor instance."""
    global _predictor
    if _predictor is None:
        _predictor = MissionPredictor()
    return _predictor


def predict_success(pass_info: Dict,
                    weather: Optional[Dict] = None,
                    config: Optional[Dict] = None) -> Dict:
    """
    Convenience function for single prediction.
    
    Args:
        pass_info: Pass data
        weather: Weather data (optional)
        config: Hardware config (optional)
    
    Returns:
        Prediction dictionary
    """
    predictor = get_predictor()
    return predictor.predict(pass_info, weather, config)


def rank_upcoming_passes(passes: List[Dict],
                         weather: Optional[Dict] = None) -> List[Dict]:
    """
    Rank passes by predicted success.
    
    Args:
        passes: List of upcoming passes
        weather: Weather data (optional)
    
    Returns:
        Ranked predictions
    """
    predictor = get_predictor()
    return predictor.rank_passes(passes, weather)


if __name__ == "__main__":
    print("ML Predictor Module")
    print("=" * 50)
    
    # Initialize predictor
    predictor = get_predictor()
    
    print("\nPredictor status:")
    status = predictor.get_status()
    for key, val in status.items():
        print(f"  {key}: {val}")
    
    # Example prediction
    print("\nExample prediction:")
    example_pass = {
        'satellite': 'NOAA 18',
        'aos_time': datetime(2026, 2, 12, 14, 30, 0),
        'los_time': datetime(2026, 2, 12, 14, 42, 0),
        'max_elevation': 65.0,
        'aos_az': 180,
        'los_az': 45,
    }
    
    pred = predictor.predict(example_pass)
    
    print(f"  Pass: {example_pass['satellite']}")
    print(f"  Max El: {example_pass['max_elevation']}°")
    print(f"  Success Probability: {pred['success_probability']:.1%}")
    print(f"  Confidence: {pred['confidence']:.1%}")
    print(f"  Method: {pred['method']}")
    print(f"  Recommendation: {pred['recommendation']}")
