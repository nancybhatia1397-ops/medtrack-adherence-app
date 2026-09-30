# 💊 MedTrack AI — Medication Adherence Tracker

An AI-powered Streamlit application for tracking medication adherence, built with **Gemini 2.5 Flash**.

---

## Features

| Feature | Details |
|---|---|
| 🔐 **Multi-role Auth** | Patients, Caregivers, Doctors |
| 💊 **Medication Management** | Add, edit, deactivate medications with dosage & frequency |
| 📋 **Dose Logging** | Mark doses as Taken / Missed / Skipped each day |
| ⏰ **Reminders** | Schedule reminder times per medication; in-app due banners |
| 📈 **Adherence Dashboard** | Plotly charts: timeline, per-med bar, calendar heatmap |
| 🤖 **AI Insights** | Gemini 2.5 Flash analysis of adherence patterns |
| 💬 **AI Chat** | Multi-turn conversational assistant about your medications |
| 👥 **Caregiver/Doctor View** | Monitor multiple patients, drill-down analytics |
| 📦 **Export** | Download adherence log & reminder schedule as CSV |

---

## Quick Start

### 1. Clone & Install

```bash
cd medication_tracker
pip install -r requirements.txt
```

### 2. Configure API Key

```bash
cp .env.example .env
# Edit .env and add your Gemini API key:
# GEMINI_API_KEY=AIza...
```

Get a free Gemini API key at [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

### 3. Run

```bash
streamlit run app.py
```

---

## Streamlit Cloud Deployment

1. Push the `medication_tracker/` folder to a GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Set **Main file path** to `app.py`.
4. Under **Secrets**, add:
   ```toml
   GEMINI_API_KEY = "AIza..."
   ```
5. Click **Deploy**.

---

## Project Structure

```
medication_tracker/
├── app.py          # Streamlit entry point & page router
├── config.py       # Constants, API key, thresholds
├── database.py     # SQLite schema & query helpers
├── auth.py         # Registration, login, session, care relationships
├── medications.py  # Medication CRUD + UI panels
├── adherence.py    # Dose logging + adherence statistics + UI
├── ai_insights.py  # Gemini 2.5 Flash insights & chat
├── reminders.py    # Reminder management + UI
├── dashboard.py    # Plotly charts & multi-patient views
└── requirements.txt
```

---

## Roles

| Role | Capabilities |
|---|---|
| **Patient** | Log doses, manage own medications, set reminders, view dashboard, chat with AI |
| **Caregiver** | Monitor linked patients, view adherence trends, AI insights per patient |
| **Doctor** | Same as Caregiver — monitor adherence, review AI-generated reports |

---

## Tech Stack

- **Frontend / App:** Streamlit
- **AI:** Google Gemini 2.5 Flash (`gemini-2.5-flash`)
- **Database:** SQLite (file-based, no setup required)
- **Charts:** Plotly Express / Graph Objects
- **Auth:** bcrypt password hashing
