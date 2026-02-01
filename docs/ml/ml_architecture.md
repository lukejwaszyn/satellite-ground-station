# ML Architecture: AI Mission Planning Subsystem

## Overview

The AI Mission Planning Subsystem extends the Autonomous Satellite Ground Station with machine learning capabilities for mission optimization, outcome prediction, and continuous learning. This transforms a passive satellite receiver into an intelligent system that improves its own performance over time.

---

## System Context

### Problem Statement

Manual mission planning for satellite reception involves:
- Reviewing pass schedules and selecting which passes to capture
- Configuring hardware settings (gain, antenna orientation)
- Monitoring captures and adjusting parameters
- Analyzing outcomes and adjusting future decisions

These tasks are time-consuming and require domain expertise. Suboptimal decisions lead to missed opportunities (skipping good passes) or wasted resources (attempting bad passes).

### Solution

An AI system that:
1. **Plans:** Automatically selects optimal passes and configurations
2. **Predicts:** Estimates success probability before each mission
3. **Adapts:** Recommends real-time adjustments during capture
4. **Learns:** Improves predictions based on outcomes

---

## Architecture

### Component Diagram

```
                    +-------------------+
                    |   Weather API     |
                    +--------+----------+
                             |
                             v
+---------------+   +--------+----------+   +------------------+
| Orbital Pred. |-->| Feature Engineer. |<--| Historical Data  |
+---------------+   +--------+----------+   +------------------+
                             |
                             v
                    +--------+----------+
                    |   Pass Scorer /   |
                    |   ML Predictor    |
                    +--------+----------+
                             |
                             v
                    +--------+----------+
                    | Schedule Optimizer|
                    +--------+----------+
                             |
                             v
                    +--------+----------+
                    | Automation &      |
                    | Control           |
                    +--------+----------+
                             |
              +--------------+--------------+
              |                             |
              v                             v
     +--------+----------+        +--------+----------+
     | Adaptive Ctrl     |        | DSP & Decoding    |
     | (real-time recs)  |        |                   |
     +--------+----------+        +--------+----------+
              |                             |
              v                             v
     +--------+----------+        +--------+----------+
     | SDR Capture       |        | Quality Metrics   |
     +-------------------+        +--------+----------+
                                           |
                                           v
                                  +--------+----------+
                                  | Model Trainer     |
                                  | (feedback loop)   |
                                  +-------------------+
```

### Data Flow

1. **Input Aggregation:** Orbital predictions + weather + historical data
2. **Feature Engineering:** Extract predictive features from raw inputs
3. **Prediction:** Score/rank passes by expected success
4. **Optimization:** Generate schedule satisfying constraints
5. **Execution:** Capture passes, monitor quality
6. **Learning:** Update models with new outcomes

---

## Component Specifications

### 1. Feature Engineering (feature_engineering.py)

**Purpose:** Transform raw data into ML-ready feature vectors

**Inputs:**
- Pass data (AOS, LOS, elevation, azimuth, satellite ID)
- Weather forecast (temperature, cloud cover, precipitation)
- Historical outcomes (previous success/failure, metrics)
- Hardware state (antenna config, LNA status)

**Outputs:**
- Feature vector per pass (pandas DataFrame or numpy array)

**Key Features:**

| Category | Feature | Type | Description |
|----------|---------|------|-------------|
| Orbital | max_elevation_deg | float | Maximum elevation during pass |
| Orbital | duration_min | float | Pass duration |
| Orbital | aos_hour | int | Hour of day (0-23) |
| Orbital | satellite_id | categorical | NOAA-15/18/19 |
| Weather | cloud_cover_pct | float | Cloud coverage |
| Weather | precip_prob | float | Precipitation probability |
| Hardware | antenna_config | categorical | CUSTOM/STOCK |
| Hardware | gain_db | float | SDR gain setting |
| Historical | recent_success_rate | float | Last 10 passes |
| Historical | elevation_bucket_success | float | Success at similar elevation |

**Implementation:**
```python
def extract_features(pass_data, weather, history, config):
    features = {}
    
    # Orbital features
    features['max_elevation_deg'] = pass_data['max_elevation']
    features['duration_min'] = (pass_data['los'] - pass_data['aos']).total_seconds() / 60
    features['aos_hour'] = pass_data['aos'].hour
    features['satellite_id'] = pass_data['satellite']
    
    # Weather features
    features['cloud_cover_pct'] = weather.get('cloud_cover', 50)
    features['precip_prob'] = weather.get('precip_prob', 0)
    
    # Hardware features
    features['antenna_config'] = config['antenna']
    features['gain_db'] = config['gain']
    
    # Historical features
    features['recent_success_rate'] = compute_recent_success(history, n=10)
    
    return pd.DataFrame([features])
```

### 2. Pass Scorer (pass_scorer.py)

**Purpose:** Rule-based pass ranking (Phase 1, no ML required)

**Algorithm:**
```python
def score_pass(features):
    score = 0.0
    
    # Elevation contributes 50% (linear scaling)
    score += (features['max_elevation_deg'] / 90) * 0.5
    
    # Weather contributes 30%
    weather_score = (1 - features['cloud_cover_pct']/100) * 0.5
    weather_score += (1 - features['precip_prob']) * 0.5
    score += weather_score * 0.3
    
    # Time diversity contributes 20%
    # Prefer spreading captures throughout day
    time_score = compute_time_diversity(features['aos_hour'])
    score += time_score * 0.2
    
    return score
```

**Tunable Parameters:**
- Elevation weight (default 0.5)
- Weather weight (default 0.3)
- Time diversity weight (default 0.2)
- Minimum elevation threshold (default 10°)

### 3. ML Predictor (ml_predictor.py)

**Purpose:** Learned prediction model (Phase 2)

**Model Selection:**
- Primary: RandomForestClassifier (interpretable, handles mixed features)
- Alternative: XGBoost (higher accuracy potential)
- Future: Neural network (if data volume warrants)

**Training Pipeline:**
```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

# Define preprocessing
numeric_features = ['max_elevation_deg', 'duration_min', 'cloud_cover_pct', 
                    'precip_prob', 'gain_db', 'recent_success_rate']
categorical_features = ['satellite_id', 'antenna_config']

preprocessor = ColumnTransformer([
    ('num', StandardScaler(), numeric_features),
    ('cat', OneHotEncoder(drop='first'), categorical_features)
])

# Create pipeline
model = Pipeline([
    ('preprocess', preprocessor),
    ('classifier', RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42))
])

# Train
model.fit(X_train, y_train)

# Validate
scores = cross_val_score(model, X, y, cv=5)
print(f"CV Accuracy: {scores.mean():.2f} +/- {scores.std():.2f}")
```

**Hyperparameter Tuning:**
- n_estimators: [50, 100, 200]
- max_depth: [5, 10, 15, None]
- min_samples_split: [2, 5, 10]

### 4. Schedule Optimizer (scheduler_optimizer.py)

**Purpose:** Generate optimal capture schedule given predictions and constraints

**Constraints:**
- Maximum captures per day (resource limit)
- Minimum time between captures (hardware cooldown)
- Priority passes (user-specified must-capture)
- Storage budget (disk space limit)

**Algorithm:**
```python
def optimize_schedule(passes, predictions, constraints):
    # Sort by predicted success probability
    ranked = sorted(zip(passes, predictions), 
                    key=lambda x: x[1], reverse=True)
    
    schedule = []
    for pass_data, prob in ranked:
        if len(schedule) >= constraints['max_per_day']:
            break
        if not conflicts_with(schedule, pass_data, constraints['min_gap']):
            schedule.append({
                'pass': pass_data,
                'predicted_success': prob,
                'priority': 'auto'
            })
    
    # Add must-capture passes regardless of prediction
    for priority_pass in constraints.get('priority_passes', []):
        if priority_pass not in [s['pass'] for s in schedule]:
            schedule.append({
                'pass': priority_pass,
                'predicted_success': None,
                'priority': 'manual'
            })
    
    return sorted(schedule, key=lambda x: x['pass']['aos'])
```

### 5. Adaptive Controller (adaptive_controller.py)

**Purpose:** Real-time monitoring and recommendations during capture

**Capabilities:**
- Monitor SNR and compare to prediction
- Detect anomalies (sudden signal drop, interference)
- Recommend gain adjustments
- Flag passes for manual review

**Implementation:**
```python
class AdaptiveController:
    def __init__(self, predicted_snr, tolerance_db=3):
        self.predicted_snr = predicted_snr
        self.tolerance_db = tolerance_db
        self.samples = []
    
    def update(self, current_snr):
        self.samples.append(current_snr)
        
        # Check for anomaly
        if current_snr < self.predicted_snr - self.tolerance_db:
            return self.generate_recommendation()
        return None
    
    def generate_recommendation(self):
        avg_snr = np.mean(self.samples[-10:])
        if avg_snr < self.predicted_snr - 5:
            return {'action': 'increase_gain', 'delta_db': 5}
        elif avg_snr < self.predicted_snr - 3:
            return {'action': 'flag_anomaly', 'message': 'SNR below expected'}
        return None
```

### 6. Model Trainer (model_trainer.py)

**Purpose:** Train and update ML models

**Training Modes:**
- **Batch:** Retrain on full dataset (daily or weekly)
- **Online:** Incremental update after each mission (future)

**Workflow:**
```python
def train_model(data_path, output_path):
    # Load data
    df = pd.read_csv(data_path)
    
    # Validate minimum samples
    if len(df) < MIN_TRAINING_SAMPLES:
        raise ValueError(f"Insufficient data: {len(df)} < {MIN_TRAINING_SAMPLES}")
    
    # Split
    X = df.drop(columns=['decode_success', 'timestamp'])
    y = df['decode_success']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    
    # Train
    model = create_pipeline()
    model.fit(X_train, y_train)
    
    # Evaluate
    metrics = evaluate_model(model, X_test, y_test)
    
    # Save
    joblib.dump(model, output_path)
    
    return metrics
```

### 7. Data Store (data_store.py)

**Purpose:** Manage historical mission data

**Schema:**
```python
mission_record = {
    'timestamp': datetime,
    'satellite_id': str,
    'aos_utc': datetime,
    'los_utc': datetime,
    'max_elevation_deg': float,
    'duration_min': float,
    'weather': {
        'cloud_cover_pct': float,
        'precip_prob': float,
        'temperature_c': float
    },
    'config': {
        'antenna': str,
        'gain_db': float,
        'lna_active': bool
    },
    'outcome': {
        'decode_success': bool,
        'snr_db': float,
        'sync_rate': float,
        'image_path': str
    },
    'prediction': {
        'predicted_success_prob': float,
        'model_version': str
    }
}
```

**Storage Format:**
- Primary: CSV (simple, portable)
- Alternative: SQLite (structured queries)
- Future: PostgreSQL (production scale)

---

## Performance Metrics

### Model Metrics
| Metric | Target | Description |
|--------|--------|-------------|
| Accuracy | >75% | Overall correct predictions |
| Precision | >70% | Correct positive predictions |
| Recall | >80% | Captured good passes |
| ROC-AUC | >0.8 | Discrimination ability |
| Calibration | <0.1 MAE | Predicted vs actual probabilities |

### Operational Metrics
| Metric | Target | Description |
|--------|--------|-------------|
| Schedule generation | <5s | Time to generate 7-day schedule |
| Prediction latency | <100ms | Time per pass prediction |
| Improvement over baseline | >10% | Success rate vs. rule-based |

---

## Data Requirements

### Minimum Viable Dataset
- 20-30 historical missions for initial training
- Balanced classes (not all successes or failures)
- Coverage of different elevations (10-90°)
- Coverage of different weather conditions

### Data Collection Strategy
1. V5 multi-pass campaign: Collect 10+ passes with varied conditions
2. Log all attempts (including failures)
3. Record weather at time of capture
4. Store all configuration parameters

---

## Deployment

### Phase 1: Rule-Based (Immediate)
- No training data required
- Deterministic scoring
- Baseline for comparison

### Phase 2: ML-Based (After V5)
- Requires 20+ historical missions
- RandomForest classifier
- Weekly batch retraining

### Phase 3: Adaptive (Future)
- Real-time recommendations
- Online learning
- Reinforcement learning exploration

---

## Future Extensions

### Generalization
- Parameterize for different mission types (not just NOAA APT)
- Support multiple ground stations
- Multi-satellite scheduling with conflicts

### Advanced ML
- Deep learning for image quality prediction
- Reinforcement learning for adaptive gain control
- Time series models for weather integration

### Startup Path
- API for external mission submission
- Multi-tenant architecture
- Commercial license model
