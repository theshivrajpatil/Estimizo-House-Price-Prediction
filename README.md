# Estimizo — Property Price Estimation Website

## Important: open this folder, not the old CasaVista project folder

1. Extract this ZIP.
2. In VS Code, choose **File → Open Folder…** and select `Estimizo-Property-Website`.
3. Stop any old Flask server in your terminal with `Ctrl+C`.
4. In the VS Code terminal, run:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```
   On Windows, activate the environment with `.venv\\Scripts\\activate`.
5. Open **http://127.0.0.1:8000**.

Check the browser tab title says **Estimizo — Property Price Estimates**. If it still says CasaVista, the old project/server is still open.

## Contact form email setup

The contact form sends enquiries through the Flask backend using SMTP. Configure these environment variables in the same terminal before starting `python app.py`:

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-sending-gmail@gmail.com"
export SMTP_PASSWORD="your-16-character-google-app-password"
export CONTACT_TO_EMAIL="theshivrajpatil@gmail.com"
```

Use your own sender Gmail and Google App Password. Do not put credentials in HTML or JavaScript. If SMTP is not configured, the contact form will show an error rather than falsely claiming the email was sent.

## Included

- `index.html`, `styles.css`, `app.js` — Estimizo website
- `app.py` — Flask app, prediction and contact endpoints
- `housing.csv` — California housing data used by the project
- `main.py`, `pipeline.pkl` — model/pipeline project files
- `.env.example` — SMTP configuration reference

The housing dataset is historical and area-level; estimates are indicative, not professional valuations.
