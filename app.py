"""
app.py – MedTrack AI: main Streamlit entry point.

Run with:
    streamlit run app.py

Environment variables (via .env or Streamlit secrets):
    GEMINI_API_KEY  – required for AI features
    DB_PATH         – optional, defaults to medication_tracker.db
"""
import streamlit as st
from database import init_db
from auth import (
    is_logged_in, current_user, clear_session, require_login,
    render_login_page,
)
from medications import render_add_medication, render_medication_list
from adherence import render_todays_doses, render_log_history, render_manual_log
from ai_insights import render_ai_insights, render_ai_chat
from reminders import render_due_banner, render_reminders_panel
from dashboard import (
    render_patient_dashboard,
    render_caregiver_overview,
    render_manage_patients,
)
from config import APP_NAME, APP_ICON, ROLES

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_NAME,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DB init ───────────────────────────────────────────────────────────────────
init_db()

# ── Auth gate ─────────────────────────────────────────────────────────────────
if not is_logged_in():
    render_login_page()
    st.stop()

user = current_user()
role = user["role"]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_NAME}")
    st.markdown(f"👤 **{user['full_name']}**")
    st.caption(f"Role: {ROLES[role]}")
    st.divider()

    if role == "patient":
        page = st.radio(
            "Navigation",
            [
                "🏠 Home",
                "📋 Today's Doses",
                "💊 My Medications",
                "⏰ Reminders",
                "📈 Dashboard",
                "🤖 AI Insights",
                "💬 AI Chat",
                "📜 Log History",
            ],
        )
    elif role in ("caregiver", "doctor"):
        page = st.radio(
            "Navigation",
            [
                "🏠 Home",
                "👥 Patient Overview",
                "🔗 Manage Patients",
                "🤖 AI Insights",
                "💬 AI Chat",
            ],
        )
    else:
        page = "🏠 Home"

    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        clear_session()
        st.rerun()

# ── Page router ───────────────────────────────────────────────────────────────

# ─── PATIENT pages ────────────────────────────────────────────────────────────
if role == "patient":
    patient_id = user["id"]

    # Show due reminder banner on every page
    render_due_banner(patient_id)

    if page == "🏠 Home":
        full_name = (user.get("full_name") or "").strip()
        first_name = full_name.split()[0] if full_name else "there"
    
        st.title(f"Welcome back, {first_name}! 👋")
        st.caption("Here's a quick snapshot of your adherence today.")
    
        from adherence import compute_adherence_rate, compute_streak
        from medications import get_medications
    
        c1, c2, c3 = st.columns(3)
            rate   = compute_adherence_rate(patient_id, 7)
        streak = compute_streak(patient_id)
        meds   = get_medications(patient_id, active_only=True)
        c1.metric("7-day Adherence", f"{rate}%")
        c2.metric("🔥 Streak",        f"{streak} day(s)")
        c3.metric("💊 Active Meds",   len(meds))

        st.divider()
        st.markdown("### 📋 Today's Quick Log")
        render_todays_doses(patient_id)

    elif page == "📋 Today's Doses":
        render_todays_doses(patient_id)

    elif page == "💊 My Medications":
        tab_list, tab_add = st.tabs(["📋 My Medications", "➕ Add Medication"])
        with tab_list:
            render_medication_list(patient_id, editable=True)
        with tab_add:
            render_add_medication(patient_id, created_by=patient_id)

    elif page == "⏰ Reminders":
        render_reminders_panel(patient_id)

    elif page == "📈 Dashboard":
        render_patient_dashboard(patient_id)

    elif page == "🤖 AI Insights":
        render_ai_insights(patient_id)

    elif page == "💬 AI Chat":
        render_ai_chat(patient_id)

    elif page == "📜 Log History":
        tab_hist, tab_manual = st.tabs(["📊 History", "✏️ Log Past Dose"])
        with tab_hist:
            render_log_history(patient_id)
        with tab_manual:
            render_manual_log(patient_id)


# ─── CAREGIVER / DOCTOR pages ─────────────────────────────────────────────────
elif role in ("caregiver", "doctor"):
    caregiver_id = user["id"]

    if page == "🏠 Home":
        st.title(f"Welcome, {ROLES[role]} {user['full_name'].split()[0]}! 👋")
        from auth import get_linked_patients
        patients = get_linked_patients(caregiver_id)
        st.metric("Patients Monitored", len(patients))
        if patients:
            st.markdown("### Quick Overview")
            render_caregiver_overview(caregiver_id)
        else:
            st.info("No patients linked yet. Go to **Manage Patients** to get started.")

    elif page == "👥 Patient Overview":
        render_caregiver_overview(caregiver_id)

    elif page == "🔗 Manage Patients":
        render_manage_patients(caregiver_id)

    elif page == "🤖 AI Insights":
        from auth import get_linked_patients
        patients = get_linked_patients(caregiver_id)
        if not patients:
            st.info("Link patients first.")
        else:
            names      = {p["full_name"]: p["id"] for p in patients}
            sel        = st.selectbox("Select Patient", list(names.keys()))
            patient_id = names[sel]
            render_ai_insights(patient_id)

    elif page == "💬 AI Chat":
        from auth import get_linked_patients
        patients = get_linked_patients(caregiver_id)
        if not patients:
            st.info("Link patients first.")
        else:
            names      = {p["full_name"]: p["id"] for p in patients}
            sel        = st.selectbox("Select Patient", list(names.keys()), key="chat_patient")
            patient_id = names[sel]
            render_ai_chat(patient_id)

# ─── Fallback ─────────────────────────────────────────────────────────────────
else:
    st.title("Unknown role")
    st.error(f"Role '{role}' is not supported.")
