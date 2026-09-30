"""
reminders.py – Reminder CRUD and Streamlit UI panel.

Reminders are stored as HH:MM strings per medication.
The app shows "due today" banners and lets users configure reminder times.
(Actual push notifications require an OS scheduler or external service;
 this module provides in-app reminders and a next-due countdown.)
"""
import streamlit as st
from datetime import datetime, time
from database import fetchall, fetchone, execute
from medications import get_medications


# ── Data helpers ──────────────────────────────────────────────────────────────

def add_reminder(medication_id: int, reminder_time: str) -> int:
    """Add a HH:MM reminder for a medication. Returns new ID."""
    # Avoid duplicates
    existing = fetchone(
        "SELECT id FROM reminders WHERE medication_id=? AND reminder_time=?",
        (medication_id, reminder_time),
    )
    if existing:
        return existing["id"]
    return execute(
        "INSERT INTO reminders (medication_id, reminder_time) VALUES (?,?)",
        (medication_id, reminder_time),
    )


def get_reminders_for_medication(medication_id: int) -> list[dict]:
    return fetchall(
        "SELECT * FROM reminders WHERE medication_id=? AND is_active=1 ORDER BY reminder_time",
        (medication_id,),
    )


def get_all_reminders_for_patient(patient_id: int) -> list[dict]:
    return fetchall(
        """SELECT r.*, m.name AS med_name, m.dosage, m.unit
           FROM reminders r
           JOIN medications m ON m.id = r.medication_id
           WHERE m.patient_id=? AND r.is_active=1 AND m.is_active=1
           ORDER BY r.reminder_time""",
        (patient_id,),
    )


def delete_reminder(reminder_id: int):
    execute("DELETE FROM reminders WHERE id=?", (reminder_id,))


def toggle_reminder(reminder_id: int, is_active: bool):
    execute("UPDATE reminders SET is_active=? WHERE id=?", (int(is_active), reminder_id))


# ── Due-check helpers ─────────────────────────────────────────────────────────

def get_due_reminders(patient_id: int, window_minutes: int = 30) -> list[dict]:
    """
    Return reminders whose scheduled time is within ±window_minutes of now.
    """
    now    = datetime.utcnow()
    now_t  = now.hour * 60 + now.minute
    all_r  = get_all_reminders_for_patient(patient_id)
    due    = []
    for r in all_r:
        try:
            h, m = map(int, r["reminder_time"].split(":"))
            diff = abs(h * 60 + m - now_t)
            if diff <= window_minutes:
                due.append(r)
        except ValueError:
            continue
    return due


def minutes_until_next(patient_id: int) -> tuple[str, int] | None:
    """
    Return (med_name, minutes_until) for the next upcoming reminder today.
    Returns None if no reminders today.
    """
    now   = datetime.utcnow()
    now_m = now.hour * 60 + now.minute
    all_r = get_all_reminders_for_patient(patient_id)
    future = []
    for r in all_r:
        try:
            h, m = map(int, r["reminder_time"].split(":"))
            sched = h * 60 + m
            if sched > now_m:
                future.append((r["med_name"], sched - now_m, r["reminder_time"]))
        except ValueError:
            continue
    if not future:
        return None
    future.sort(key=lambda x: x[1])
    name, diff, t = future[0]
    return name, diff, t


# ── Streamlit UI ──────────────────────────────────────────────────────────────

def render_due_banner(patient_id: int):
    """Show a prominent banner if any dose is due within 30 min."""
    due = get_due_reminders(patient_id, window_minutes=30)
    if due:
        names = ", ".join(r["med_name"] for r in due)
        st.warning(f"⏰ **Reminder:** Time to take **{names}**!", icon="💊")

    nxt = minutes_until_next(patient_id)
    if nxt:
        name, mins, t = nxt
        if mins > 0:
            st.info(f"🕐 Next dose: **{name}** at {t} (in {mins} min)")


def render_reminders_panel(patient_id: int):
    st.subheader("⏰ Reminder Manager")

    meds = get_medications(patient_id, active_only=True)
    if not meds:
        st.info("Add medications first to set up reminders.")
        return

    # Add reminder form
    st.markdown("##### Add a Reminder Time")
    with st.form("add_reminder_form", clear_on_submit=True):
        med_options = {f"{m['name']} ({m['frequency']})": m["id"] for m in meds}
        selected    = st.selectbox("Medication", list(med_options.keys()))
        rem_time    = st.time_input("Reminder Time", value=time(8, 0))
        if st.form_submit_button("➕ Add Reminder"):
            med_id = med_options[selected]
            rid    = add_reminder(med_id, rem_time.strftime("%H:%M"))
            st.success(f"Reminder set at {rem_time.strftime('%H:%M')} for {selected.split(' (')[0]}.")
            st.rerun()

    st.markdown("---")
    st.markdown("##### Your Scheduled Reminders")

    all_reminders = get_all_reminders_for_patient(patient_id)
    if not all_reminders:
        st.info("No reminders configured yet.")
        return

    for r in all_reminders:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.write(f"💊 **{r['med_name']}** — {r['dosage']} {r['unit']}")
        with col2:
            st.write(f"🕐 {r['reminder_time']}")
        with col3:
            if st.button("🗑️", key=f"del_rem_{r['id']}", help="Delete reminder"):
                delete_reminder(r["id"])
                st.rerun()

    # Export summary
    st.markdown("---")
    import pandas as pd
    df = pd.DataFrame(all_reminders)[["med_name", "dosage", "unit", "reminder_time"]]
    df.columns = ["Medication", "Dosage", "Unit", "Time"]
    csv = df.to_csv(index=False)
    st.download_button("⬇️ Export Reminder Schedule", csv, "reminders.csv", "text/csv")
