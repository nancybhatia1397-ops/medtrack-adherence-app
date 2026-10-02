import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini API ────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = "gemini-3.8-flash"

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "medication_tracker.db")

# ── App metadata ──────────────────────────────────────────────────────────────
APP_NAME    = "MedTrack AI"
APP_VERSION = "1.0.0"
APP_ICON    = "💊"

# ── Roles ─────────────────────────────────────────────────────────────────────
ROLES = {
    "patient":   "Patient",
    "caregiver": "Caregiver",
    "doctor":    "Doctor / Physician",
}

# ── Adherence thresholds (%) ──────────────────────────────────────────────────
ADHERENCE_EXCELLENT = 90
ADHERENCE_GOOD      = 75
ADHERENCE_POOR      = 50

# ── Medication frequencies ────────────────────────────────────────────────────
FREQUENCIES = [
    "Once daily",
    "Twice daily",
    "Three times daily",
    "Four times daily",
    "Every other day",
    "Weekly",
    "As needed (PRN)",
]

# ── Common medication units ───────────────────────────────────────────────────
UNITS = ["mg", "mcg", "g", "ml", "IU", "tablet(s)", "capsule(s)", "drop(s)", "patch(es)", "puff(s)"]

# ── Timezone default ──────────────────────────────────────────────────────────
DEFAULT_TIMEZONE = "UTC"
