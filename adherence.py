"""
adherence.py – Dose logging, adherence statistics, and Streamlit log panel.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import fetchall, fetchone, execute
from medications import get_medications
from config import ADHERENCE_EXCELLENT, ADHERENCE_GOOD, ADHERENCE_POOR


# ── Logging helpers ───────────────────────────────────────────────────────────

def log_dose(medication_id: int, patient_id: int, scheduled_for: str,
             status: str, notes: str = "", taken_at: str | None = None) -> int:
    """Insert a single dose log entry."""
    if taken_at is None and status == "taken":
        taken_at = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    return execute(
        """INSERT INTO adherence_logs
           (medication_id, patient_id, scheduled_for, taken_at, status, notes)
           VALUES (?,?,?,?,?,?)""",
        (medication_id, patient_id, scheduled_for, taken_at, status, notes),
    )


def get_logs(patient_id: int, days: int = 30) -> list[dict]:
    since = (datetime.utcnow() - timedelta(days=days)).isoformat(sep=" ", timespec="seconds")
    return fetchall(
        """SELECT al.*, m.name AS med_name, m.dosage, m.unit
           FROM adherence_logs al
           JOIN medications m ON m.id = al.medication_id
           WHERE al.patient_id=? AND al.logged_at >= ?
           ORDER BY al.scheduled_for DESC""",
        (patient_id, since),
    )


def get_logs_dataframe(patient_id: int, days: int = 30) -> pd.DataFrame:
    logs = get_logs(patient_id, days)
    if not logs:
        return pd.DataFrame()
    return pd.DataFrame(logs)


def already_logged(medication_id: int, scheduled_for: str) -> bool:
    row = fetchone(
        "SELECT id FROM adherence_logs WHERE medication_id=? AND scheduled_for=?",
        (medication_id, scheduled_for),
    )
    return row is not None


# ── Statistics ────────────────────────────────────────────────────────────────

def compute_adherence_rate(patient_id: int, days: int = 30) -> float:
    """Return overall adherence % (taken / (taken + missed)) over last N days."""
    logs = get_logs(patient_id, days)
    if not logs:
        return 0.0
    taken  = sum(1 for l in logs if l["status"] == "taken")
    missed = sum(1 for l in logs if l["status"] == "missed")
    total  = taken + missed
    return round((taken / total * 100) if total else 0.0, 1)


def compute_per_medication_rates(patient_id: int, days: int = 30) -> pd.DataFrame:
    logs = get_logs(patient_id, days)
    if not logs:
        return pd.DataFrame(columns=["Medication", "Taken", "Missed", "Skipped", "Rate (%)"])
    df = pd.DataFrame(logs)
    grouped = df.groupby("med_name")["status"].value_counts().unstack(fill_value=0)
    for col in ["taken", "missed", "skipped"]:
        if col not in grouped.columns:
            grouped[col] = 0
    grouped["total"]    = grouped["taken"] + grouped["missed"]
    grouped["Rate (%)"] = (grouped["taken"] / grouped["total"].replace(0, 1) * 100).round(1)
    grouped = grouped.reset_index().rename(columns={
        "med_name": "Medication",
        "taken":    "Taken",
        "missed":   "Missed",
        "skipped":  "Skipped",
    })
    return grouped[["Medication", "Taken", "Missed", "Skipped", "Rate (%)"]]


def adherence_badge(rate: float) -> str:
    if rate >= ADHERENCE_EXCELLENT:
        return f"🟢 Excellent ({rate}%)"
    elif rate >= ADHERENCE_GOOD:
        return f"🟡 Good ({rate}%)"
    elif rate >= ADHERENCE_POOR:
        return f"🟠 Fair ({rate}%)"
    else:
        return f"🔴 Poor ({rate}%)"


def compute_streak(patient_id: int) -> int:
    """Return current consecutive days with ≥1 taken dose."""
    rows = fetchall(
        """SELECT DATE(scheduled_for) AS day, status
           FROM adherence_logs
           WHERE patient_id=? AND status='taken'
           ORDER BY day DESC""",
        (patient_id,),
    )
    if not rows:
        return 0
    days_with_taken = sorted({r["day"] for r in rows}, reverse=True)
    streak = 0
    check  = date.today()
    for d in days_with_taken:
        if d == check.isoformat():
            streak += 1
            check  -= timedelta(days=1)
        else:
            break
    return streak


# ── Streamlit UI: Today's Dose Panel ─────────────────────────────────────────

def render_todays_doses(patient_id: int):
    st.subheader("📋 Today's Medications")
    meds = get_medications(patient_id, active_only=True)

    if not meds:
        st.info("No active medications. Add medications first.")
        return

    today_str = date.today().isoformat()

    for med in meds:
        scheduled_for = f"{today_str} 00:00:00"
        logged        = already_logged(med["id"], scheduled_for)

        label = f"**{med['name']}** — {med['dosage']} {med['unit']} | {med['frequency']}"
        with st.expander(label + (" ✅" if logged else " ⏳")):
            if med["instructions"]:
                st.caption(f"📌 {med['instructions']}")

            if logged:
                st.success("Already logged for today.")
            else:
                col1, col2, col3 = st.columns(3)
                notes = st.text_input("Notes (optional)", key=f"notes_{med['id']}")
                with col1:
                    if st.button("✅ Taken", key=f"taken_{med['id']}", use_container_width=True):
                        log_dose(med["id"], patient_id, scheduled_for, "taken", notes)
                        st.success("Dose marked as taken!")
                        st.rerun()
                with col2:
                    if st.button("❌ Missed", key=f"missed_{med['id']}", use_container_width=True):
                        log_dose(med["id"], patient_id, scheduled_for, "missed", notes)
                        st.warning("Dose marked as missed.")
                        st.rerun()
                with col3:
                    if st.button("⏭️ Skipped", key=f"skip_{med['id']}", use_container_width=True):
                        log_dose(med["id"], patient_id, scheduled_for, "skipped", notes)
                        st.info("Dose marked as skipped.")
                        st.rerun()


# ── Streamlit UI: Log History ─────────────────────────────────────────────────

def render_log_history(patient_id: int):
    st.subheader("📊 Adherence Log History")
    days = st.slider("Show logs for the last N days", 7, 90, 30)
    df   = get_logs_dataframe(patient_id, days)

    if df.empty:
        st.info("No logs found for the selected period.")
        return

    # Colour-coded status
    status_map = {"taken": "✅ Taken", "missed": "❌ Missed", "skipped": "⏭️ Skipped"}
    df["Status"] = df["status"].map(status_map)
    display = df[["scheduled_for", "med_name", "dosage", "unit", "Status", "notes"]].copy()
    display.columns = ["Scheduled", "Medication", "Dosage", "Unit", "Status", "Notes"]
    st.dataframe(display, use_container_width=True)

    # Download
    csv = display.to_csv(index=False)
    st.download_button("⬇️ Download CSV", csv, "adherence_log.csv", "text/csv")


# ── Streamlit UI: Manual Past-Dose Logger ─────────────────────────────────────

def render_manual_log(patient_id: int):
    st.subheader("✏️ Log Past Dose")
    meds = get_medications(patient_id, active_only=True)
    if not meds:
        st.info("No active medications.")
        return

    med_names = {m["name"]: m["id"] for m in meds}
    with st.form("manual_log_form", clear_on_submit=True):
        med_name      = st.selectbox("Medication", list(med_names.keys()))
        log_date      = st.date_input("Date", value=date.today())
        log_status    = st.selectbox("Status", ["taken", "missed", "skipped"])
        log_notes     = st.text_area("Notes")
        submitted     = st.form_submit_button("📝 Log Dose")

    if submitted:
        med_id        = med_names[med_name]
        scheduled_for = f"{log_date.isoformat()} 00:00:00"
        if already_logged(med_id, scheduled_for):
            st.warning("A log for this medication on this date already exists.")
        else:
            log_dose(med_id, patient_id, scheduled_for, log_status, log_notes)
            st.success("Dose logged.")
            st.rerun()
