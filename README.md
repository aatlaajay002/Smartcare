# AI-Powered Smart Healthcare Appointment & Assistance System
**Author:** Aatla Ajay

A full-stack web application where users can **book doctor appointments**, get a **doctor recommendation from their symptoms (Machine Learning)** and get **medical reports explained in simple words (Generative AI)**.

## Two portals, two roles
| Role | Where they land after login | What they can do |
|---|---|---|
| **Patient (user)** | Patient website | Doctors, Patient Dashboard, Symptom Checker (ML), AI Health Assistant, Report Explainer (GenAI), Appointments |
| **Admin** | **Admin Portal** (`/admin`) | Monitor overview + AI usage, all appointments, add/edit/delete doctors, patients, activity log |

**Admin login (auto-created on first run):** `admin@smartcare.com` / `Admin@123` - change it in `Backend/.env` (`ADMIN_EMAIL`, `ADMIN_PASSWORD`) before you submit or deploy.
Patients can never open the Admin Portal: admin pages and APIs are protected **on the server** (403 for patients). Public registration always creates a patient account and requires a valid 10-digit phone number.

## Features
| Module | What it does |
|---|---|
| **Appointment system** | Login page first, then Home / Doctors / Symptom Checker / Report Explainer / My Appointments; register / login, doctor listing (name, specialization, availability), slot-based booking with double-booking protection, appointment history + cancel |
| **Patient Dashboard** | Total / upcoming / completed / cancelled appointments and the next visit |
| **AI Health Assistant** | Chat (LLM + ML): health guidance, red-flag warnings, suggests a specialist and lets you book directly |
| **Machine Learning** | User types symptoms -> **Logistic Regression** (TF-IDF) predicts the specialization -> matching doctors are shown with a *Book* button |
| **Generative AI** | User pastes a report or uploads `.txt / .pdf / .docx` -> LLM API returns a simple, easy-to-understand explanation |

## Tech stack
Frontend: HTML, CSS, JavaScript | Backend: Flask (Python) | Database: MySQL (SQLite also supported) | ML: scikit-learn | GenAI: LLM API (Claude / Gemini / OpenAI)

## Project structure
```
AatlaAjay_SmartCare/
├── Frontend/                 HTML, CSS, JS (served by Flask)
│   ├── index.html            login page + patient website
│   ├── css/style.css, js/app.js
│   └── admin/                Admin Portal (index.html, admin.css, admin.js) - served to admins only
├── Backend/                  APIs + ML + GenAI integration
│   ├── app.py                Flask app & REST endpoints
│   ├── db.py                 MySQL / SQLite layer + seed doctors
│   ├── ml_service.py         loads saved model, predicts specialization
│   ├── genai_service.py      LLM API call, file text extraction
│   ├── config.py, requirements.txt, .env.example
├── ML/                       training code, dataset, saved model
│   ├── Symptom_Doctor_Recommendation.ipynb   (preprocessing, training, evaluation)
│   ├── generate_dataset.py, train_model.py, text_utils.py
│   ├── symptom_dataset.csv   (dataset used)
│   ├── symptom_model.joblib  (saved model)
│   └── metrics.json, confusion_matrix.png
├── sample_reports/           ready-made reports for the GenAI demo
├── Project_Documentation.docx / .pdf
├── DEMO_GUIDE.md             demo script + viva Q&A
└── README.md
```

## Quick start (easiest): double-click `run.bat`
It creates the environment, installs everything, starts the app and opens your browser at the correct address.
If you ever see an OLD design, an old copy is still running: close every black Command Prompt window and run `run.bat` again (it prints the exact address to open).

## Setup & run manually (5 minutes)
Requires **Python 3.9+**.

```bash
cd Backend
python -m venv venv
venv\Scripts\activate            # Windows      (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Windows      (Mac/Linux: cp .env.example .env)
python app.py
```
Open **http://127.0.0.1:5000** in your browser - the **login / register page appears first**; the website opens after you log in. Tables and 28 sample doctors are created automatically on first run. The trained model is already included.

### Use MySQL (instead of SQLite)
1. Start MySQL. 2. Edit `Backend/.env`:
```
DB_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=smart_healthcare
```
The database and tables are created automatically.

### Enable the Generative AI feature
Put **one** API key in `Backend/.env` (provider is auto-detected):
```
GEMINI_API_KEY=...      # free key: https://aistudio.google.com/apikey
# or ANTHROPIC_API_KEY=...  or  OPENAI_API_KEY=...
```
Restart the app. The result card shows which model generated the explanation. Without a key, the app falls back to a basic **offline mode** (clearly labelled) so it never crashes.

### Re-train the ML model (optional)
```bash
cd ML
python generate_dataset.py     # creates symptom_dataset.csv
python train_model.py          # trains, evaluates, saves symptom_model.joblib
```
Or open `ML/Symptom_Doctor_Recommendation.ipynb` in Jupyter.

## ML results (test set, 840 rows)
Accuracy **95.1%** | Macro-F1 **0.951** | 5-fold CV **94.1%**.
> The dataset is **synthetic** (generated from a symptom knowledge base with realistic noise) - for demonstration only, not medical use.

## API endpoints
`POST /api/register` `POST /api/login` `POST /api/logout` `GET /api/me` `GET /api/doctors` `GET /api/specializations` `GET /api/doctors/<id>/slots?date=YYYY-MM-DD` `POST /api/appointments` `GET /api/appointments` `POST /api/appointments/<id>/cancel` `POST /api/predict` `POST /api/summarize` `POST /api/assistant` `GET /api/dashboard` `GET /api/health`
**Admin only:** `GET /api/admin/stats` `GET /api/admin/users` `DELETE /api/admin/users/<id>` `GET /api/admin/appointments` `POST /api/admin/appointments/<id>/cancel` `GET|POST /api/admin/doctors` `PUT|DELETE /api/admin/doctors/<id>` `GET /api/admin/activity`

## Troubleshooting
* *"Model not found"* -> run `python train_model.py` inside `ML/`.
* *MySQL connection error* -> check `.env` credentials, or set `DB_TYPE=sqlite`.
* *Report shows "Offline mode"* -> no/invalid API key in `Backend/.env`; restart after editing.
* *Cannot log in as admin* -> check `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `Backend/.env` (the admin is created on first start; restart after editing).
* *Upgrading from an older version* -> your existing database is upgraded automatically (a `role` column is added).
* `http://127.0.0.1:5000/api/health` shows the active database and LLM provider.

> Disclaimer: for information only - not a substitute for professional medical advice.
