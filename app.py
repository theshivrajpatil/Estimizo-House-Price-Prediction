"""Flask API and static server for the Estimizo property estimator."""
from pathlib import Path
import subprocess
import sys
import math
import os
import re
import smtplib
from email.message import EmailMessage

import joblib
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"
PIPELINE_PATH = BASE_DIR / "pipeline.pkl"
MAIN_PATH = BASE_DIR / "main.py"
FEATURES = [
    "longitude",
    "latitude",
    "housing_median_age",
    "total_rooms",
    "total_bedrooms",
    "population",
    "households",
    "median_income",
    "ocean_proximity",
]
OCEAN_VALUES = {"<1H OCEAN", "INLAND", "ISLAND", "NEAR BAY", "NEAR OCEAN"}

app = Flask(__name__, static_folder=None)
_model = None
_pipeline = None
_housing_data = None

# City coordinates are used to find nearby communities in the supplied California housing data.
CITY_COORDINATES = {
    "san-francisco": ("San Francisco", -122.42, 37.77),
    "san-jose": ("San Jose", -121.89, 37.34),
    "oakland": ("Oakland", -122.27, 37.80),
    "los-angeles": ("Los Angeles", -118.24, 34.05),
    "san-diego": ("San Diego", -117.16, 32.72),
    "santa-barbara": ("Santa Barbara", -119.70, 34.42),
    "sacramento": ("Sacramento", -121.49, 38.58),
    "fresno": ("Fresno", -119.79, 36.74),
}


def get_housing_data():
    """Load the supplied housing records once for local market comparisons."""
    global _housing_data
    if _housing_data is None:
        _housing_data = pd.read_csv(BASE_DIR / "housing.csv")
    return _housing_data


def estimate_from_local_data(location_key, area, bedrooms, bathrooms):
    """Estimate an indicative size-adjusted range from nearby recorded values.

    The source data describes community-level median values, not individual homes or
    square footage. Size adjustment is therefore a conservative heuristic, not a
    learned price-per-square-foot relationship.
    """
    if location_key not in CITY_COORDINATES:
        raise ValueError("Choose a valid California location.")
    area = float(area)
    bedrooms = int(bedrooms)
    bathrooms = float(bathrooms)
    if not math.isfinite(area) or not 250 <= area <= 20000:
        raise ValueError("Property area must be between 250 and 20,000 square feet.")
    if not 1 <= bedrooms <= 6:
        raise ValueError("Choose between 1 and 6 bedrooms.")
    if not 1 <= bathrooms <= 4:
        raise ValueError("Choose between 1 and 4 bathrooms.")

    _, longitude, latitude = CITY_COORDINATES[location_key]
    data = get_housing_data()
    # Approximate geographic distance in degrees, corrected for longitude at this latitude.
    dx = (data["longitude"] - longitude) * math.cos(math.radians(latitude))
    dy = data["latitude"] - latitude
    nearby = data.loc[(dx * dx + dy * dy) <= (0.12 ** 2), "median_house_value"].dropna()
    if len(nearby) < 10:
        nearby = data["median_house_value"].dropna()

    # Scale the nearby community-value distribution conservatively by floor area.
    size_factor = (area / 1500.0) ** 0.65
    room_factor = 1 + 0.035 * (bedrooms - 3) + 0.015 * (bathrooms - 2)
    factor = size_factor * max(0.82, min(1.18, room_factor))
    lower = float(nearby.quantile(0.25)) * factor
    typical = float(nearby.median()) * factor
    upper = float(nearby.quantile(0.75)) * factor

    # Source target values are capped at $500,001; do not imply precision beyond the data.
    cap = 500001.0
    return {
        "prediction": round(min(cap, max(15000.0, typical))),
        "lower": round(min(cap, max(15000.0, lower))),
        "upper": round(min(cap, max(15000.0, upper))),
        "location": CITY_COORDINATES[location_key][0],
    }


def load_predictor():
    """Load the saved model; train through the project's existing script if absent."""
    global _model, _pipeline
    if _model is not None and _pipeline is not None:
        return _model, _pipeline

    if not MODEL_PATH.exists() or not PIPELINE_PATH.exists():
        if not (BASE_DIR / "housing.csv").exists() or not MAIN_PATH.exists():
            raise FileNotFoundError(
                "Model files are missing. Place app.py alongside housing.csv, main.py, "
                "and pipeline.pkl so the model can be trained."
            )
        completed = subprocess.run(
            [sys.executable, str(MAIN_PATH)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not MODEL_PATH.exists() or not PIPELINE_PATH.exists():
            details = (completed.stderr or completed.stdout or "Model training failed.").strip()
            raise RuntimeError(details[-1200:])

    _model = joblib.load(MODEL_PATH)
    _pipeline = joblib.load(PIPELINE_PATH)
    return _model, _pipeline


@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    if filename in {"styles.css", "app.js"}:
        return send_from_directory(BASE_DIR, filename)
    return jsonify({"error": "Not found."}), 404


@app.get("/health")
def health():
    return jsonify({"status": "ok", "model_loaded": _model is not None})


@app.post("/estimate")
def estimate():
    """Return a simple property estimate based on nearby values and floor area."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send property details as a JSON object."}), 400
    try:
        result = estimate_from_local_data(
            str(payload.get("location", "")),
            payload.get("area", 0),
            payload.get("bedrooms", 3),
            payload.get("bathrooms", 2),
        )
        return jsonify(result)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Property estimate failed")
        return jsonify({"error": "The estimate service is not ready. Check the backend logs."}), 500


@app.post("/contact")
def contact():
    """Send a visitor enquiry to the site owner's configured email address."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send your enquiry as a JSON object."}), 400

    sender_name = str(payload.get("sender_name", "")).strip()
    sender_email = str(payload.get("sender_email", "")).strip()
    message_text = str(payload.get("message", "")).strip()
    if not sender_name or len(sender_name) > 100:
        return jsonify({"error": "Enter your name (up to 100 characters)."}), 400
    if not sender_email or len(sender_email) > 150 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", sender_email):
        return jsonify({"error": "Enter a valid email address."}), 400
    if not message_text or len(message_text) > 2000:
        return jsonify({"error": "Write a message of up to 2,000 characters."}), 400

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    recipient = os.getenv("CONTACT_TO_EMAIL", "theshivrajpatil@gmail.com").strip()
    if not smtp_user or not smtp_password:
        return jsonify({"error": "Email delivery is not configured yet. Please configure SMTP_USER and SMTP_PASSWORD on the server."}), 503

    email = EmailMessage()
    email["Subject"] = f"Estimizo website enquiry from {sender_name}"
    email["From"] = smtp_user
    email["To"] = recipient
    email["Reply-To"] = sender_email
    email.set_content(
        f"New enquiry received through Estimizo.\n\n"
        f"Name: {sender_name}\nEmail: {sender_email}\n\n"
        f"Question:\n{message_text}\n"
    )
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(email)
    except (OSError, smtplib.SMTPException) as exc:
        app.logger.error("Contact email delivery failed: %s", exc)
        return jsonify({"error": "Email could not be sent right now. Please try again later."}), 502

    return jsonify({"message": "Your message has been sent successfully."}), 200


@app.post("/predict")
def predict():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Send property details as a JSON object."}), 400

    missing = [key for key in FEATURES if key not in payload]
    if missing:
        return jsonify({"error": "Missing required fields: " + ", ".join(missing)}), 400

    try:
        row = {key: payload[key] for key in FEATURES}
        for key in FEATURES[:-1]:
            row[key] = float(row[key])
            if not pd.notna(row[key]):
                raise ValueError(f"{key} must be a finite number.")
        if row["ocean_proximity"] not in OCEAN_VALUES:
            raise ValueError("Choose a valid ocean proximity category.")
        if not -125 <= row["longitude"] <= -113:
            raise ValueError("Longitude must be between -125 and -113 for California." )
        if not 32 <= row["latitude"] <= 42.5:
            raise ValueError("Latitude must be between 32 and 42.5 for California.")
        if row["housing_median_age"] <= 0 or row["total_rooms"] <= 0:
            raise ValueError("Home age and total rooms must be greater than zero.")
        if row["total_bedrooms"] < 0 or row["population"] <= 0 or row["households"] <= 0:
            raise ValueError("Bedrooms cannot be negative; population and households must be positive.")
        if row["total_bedrooms"] > row["total_rooms"]:
            raise ValueError("Total bedrooms cannot exceed total rooms.")
        if row["households"] > row["population"]:
            raise ValueError("Households cannot exceed population.")
        if row["median_income"] <= 0:
            raise ValueError("Median income must be greater than zero and use the dataset scale.")

        model, pipeline = load_predictor()
        features = pd.DataFrame([row], columns=FEATURES)
        transformed = pipeline.transform(features)
        value = float(model.predict(transformed)[0])
        return jsonify({"prediction": round(max(0.0, value), 2)})
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # Keep implementation details out of the browser response.
        app.logger.exception("Prediction request failed")
        return jsonify({"error": "Prediction service is not ready. Check the backend logs and model files."}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
