import pandas as pd
import joblib
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Project directory
PROJECT_DIR = Path(__file__).resolve().parent

# File paths
DATA_FILE = PROJECT_DIR / "housing.csv"
MODEL_FILE = PROJECT_DIR / "model.pkl"
PIPELINE_FILE = PROJECT_DIR / "pipeline.pkl"
OUTPUT_FILE = PROJECT_DIR / "model_evaluation_results.txt"

# Load dataset
data = pd.read_csv(DATA_FILE)

# Separate features and target
X = data.drop("median_house_value", axis=1)
y = data["median_house_value"]

# Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Load trained model and preprocessing pipeline
model = joblib.load(MODEL_FILE)
pipeline = joblib.load(PIPELINE_FILE)

# Prepare test data and make predictions
X_test_prepared = pipeline.transform(X_test)
y_pred = model.predict(X_test_prepared)

# Calculate evaluation metrics
mae = mean_absolute_error(y_test, y_pred)
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)
r2 = r2_score(y_test, y_pred)

# Format results
results = f"""
========================================
  ESTIMIZO MODEL EVALUATION RESULTS
========================================

Model: California House Price Prediction

Evaluation Metrics
------------------
MAE       : ${mae:,.2f}
MSE       : {mse:,.2f}
RMSE      : ${rmse:,.2f}
R² Score  : {r2:.4f} ({r2 * 100:.2f}%)

Interpretation
--------------
MAE:
Average absolute difference between actual
and predicted house prices.

MSE:
Average squared prediction error.

RMSE:
Prediction error measured in the target's
units (dollars), with greater sensitivity
to larger errors.

R² Score:
Proportion of variation in house prices
explained by the model on the test dataset.

Note:
Results describe performance on this test
split. They do not guarantee real-world
prediction accuracy.

========================================
"""

# Print results in terminal
print(results)

# Save results directly into the project folder
with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
    file.write(results)

print(f"Results saved to: {OUTPUT_FILE}")