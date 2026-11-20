# Demo Guide (5-10 min) + Viva Q&A

## Before you start
1. `cd Backend` -> activate venv -> `python app.py`
2. Check `http://127.0.0.1:5000/api/health` -> should show your DB (`mysql`) and LLM (`gemini` / `anthropic` / `openai`).
3. Keep `sample_reports/report1_diabetes.txt` ready to upload.

## Demo flow
| Time | Show | Say |
|---|---|---|
| 0:00 | Problem + stack slide / README | 3 modules: booking, ML recommendation, GenAI explanation |
| 0:45 | **Login page opens first** -> Register a new user -> you are taken inside the website | Website is only visible after login; passwords are hashed; session-based auth; Logout returns to the login page |
| 1:15 | **Home page** (28 doctors, 14 specializations) -> **Doctors** - search, filter by specialization | Name, specialization, availability come from the database |
| 2:15 | **Book** a doctor: pick date -> slots -> confirm | Slots are generated from availability; booked slots disappear; server re-checks to stop double-booking |
| 3:15 | **My Appointments** -> cancel one | History + cancel; cancelled slot becomes free again |
| 4:00 | **Symptom Checker**: "chest pain, palpitations and dizziness" -> then try "itchy skin rash", "burning during urination" | ML model predicts specialization with confidence %; matching doctors shown; book directly from result |
| 5:30 | **Report Explainer**: paste `Type 2 Diabetes. Metformin 500mg twice daily. Avoid sugar. Regular exercise.` then upload `report1_diabetes.txt` | LLM API generates the explanation - nothing hard-coded; badge shows which model answered |
| 7:00 | **Code walkthrough**: `ml_service.py` (loads joblib) -> `genai_service.py` (prompt + API) -> `app.py` (endpoints) -> notebook (accuracy 95%) | Show integration points |

## Admin Portal demo (add 2-3 minutes)
1. Logout, then log in with the **admin** account (`admin@smartcare.com` / `Admin@123`) - you land on the **Admin Portal**, not the patient site.
2. **Overview**: totals, 7-day appointments chart, bookings by specialization, **AI usage counters** and recent activity (these numbers update as patients use the app).
3. **Appointments**: search / filter, cancel one. **Doctors**: add a doctor, edit timings. **Patients**: list. **Activity Log**: every login, booking and AI request.
4. Show security: log in as a patient and open `/admin` -> you are sent back to the website; the admin APIs return 403.

## Likely viva questions
* **How do you keep users out of the admin portal?** A `role` column (user/admin). Public sign-up always creates `user`. Every admin API has an `@admin_required` check on the server (401 not logged in, 403 for patients) and the `/admin` page and its JS/CSS are served only to admins - hiding a button is not the security.
* **What does the admin monitor?** Users, doctors, appointments and AI usage counts. The activity log stores only the action type - never report text or chat messages (privacy).
* **How does the AI Assistant work?** ML model checks if the message describes symptoms and predicts the specialization; the LLM writes a short safe answer (no diagnosis/doses, emergency warning for red flags); the app then offers doctors to book.
* **Why Logistic Regression?** Required by the task; it is fast, works well on sparse TF-IDF text features, gives probabilities (confidence) and is interpretable (coefficients show which words matter).
* **What is TF-IDF?** Converts text to numbers: words frequent in one text but rare overall get higher weight. Bigrams capture phrases like "chest pain".
* **How did you evaluate?** 80/20 stratified split + 5-fold CV; accuracy 95.1%, macro-F1 0.951, confusion matrix, per-class report.
* **Where does the data come from?** Generated from a symptom-per-specialization knowledge base with shared symptoms, noise symptoms and 3% label noise (`generate_dataset.py`). Be honest: it's synthetic; real data would be the next step.
* **How is the model integrated?** Saved with joblib; `ml_service.py` loads it once and `/api/predict` returns top-3 predictions + doctors.
* **How do you avoid hard-coding AI output?** Report text -> prompt -> LLM API -> response. Prompt tells the model to use only facts in the report.
* **What if the LLM API fails?** Falls back to a labelled offline rule-based simplifier; the app keeps working.
* **How do you prevent double booking?** Server regenerates the free slots and rejects a booking if the slot is taken (HTTP 409).
* **How is security handled?** Hashed passwords (Werkzeug), server-side validation, HTML escaping in the frontend, parameterised SQL queries (no SQL injection).
* **Limitations?** Synthetic data; suggests specialization only (not a diagnosis); no real-time doctor calendar sync.
