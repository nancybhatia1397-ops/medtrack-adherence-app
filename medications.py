"""
medications.py – CRUD for patient medications and Streamlit UI panels.
"""
import streamlit as st
from datetime import date
from database import fetchall, fetchone, execute
from config import FREQUENCIES, UNITS


# ── Data helpers ──────────────────────────────────────────────────────────────

def add_medication(patient_id: int, name: str, dosage: str, unit: str,
                   frequency: str, instructions: str,
                   start_date: str, end_date: str | None,
                   created_by: int) -> int:
    return execute(
        """INSERT INTO medications
           (patient_id, name, dosage, unit, frequency, instructions,
            start_date, end_date, created_by)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (patient_id, name, dosage, unit, frequency, instructions,
         start_date, end_date, created_by),
    )


def get_medications(patient_id: int, active_only: bool = True) -> list[dict]:
    query = "SELECT * FROM medications WHERE patient_id=?"
    params: tuple = (patient_id,)
    if active_only:
        query += " AND is_active=1"
    query += " ORDER BY name"
    return fetchall(query, params)


def get_medication_by_id(med_id: int) -> dict | None:
    return fetchone("SELECT * FROM medications WHERE id=?", (med_id,))


def update_medication(med_id: int, name: str, dosage: str, unit: str,
                      frequency: str, instructions: str,
                      end_date: str | None, is_active: int):
    execute(
        """UPDATE medications SET name=?, dosage=?, unit=?, frequency=?,
           instructions=?, end_date=?, is_active=?
           WHERE id=?""",
        (name, dosage, unit, frequency, instructions, end_date, is_active, med_id),
    )


def deactivate_medication(med_id: int):
    execute("UPDATE medications SET is_active=0 WHERE id=?", (med_id,))


def delete_medication(med_id: int):
    execute("DELETE FROM medications WHERE id=?", (med_id,))


# ── Streamlit UI ──────────────────────────────────────────────────────────────

def render_add_medication(patient_id: int, created_by: int):
    st.subheader("➕ Add New Medication")
    with st.form("add_med_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name        = st.text_input("Medication Name *", placeholder="e.g. Metformin")
            dosage      = st.text_input("Dosage *", placeholder="e.g. 500")
            unit        = st.selectbox("Unit", UNITS)
            frequency   = st.selectbox("Frequency", FREQUENCIES)
        with col2:
            start_date  = st.date_input("Start Date", value=date.today())
            end_date_on = st.checkbox("Has end date?")
            end_date    = st.date_input("End Date") if end_date_on else None
            instructions = st.text_area("Instructions / Notes", placeholder="Take with food…", height=100)
        submitted = st.form_submit_button("💾 Save Medication", use_container_width=True)

    if submitted:
        if not name.strip() or not dosage.strip():
            st.error("Medication name and dosage are required.")
            return
        med_id = add_medication(
            patient_id, name.strip(), dosage.strip(), unit, frequency,
            instructions.strip(),
            start_date.isoformat(),
            end_date.isoformat() if end_date else None,
            created_by,
        )
        st.success(f"✅ {name} added (ID #{med_id}).")
        st.rerun()


def render_medication_list(patient_id: int, editable: bool = True):
    st.subheader("💊 Current Medications")
    meds = get_medications(patient_id, active_only=True)

    if not meds:
        st.info("No active medications found.")
        return

    for med in meds:
        with st.expander(f"💊 {med['name']}  —  {med['dosage']} {med['unit']}  |  {med['frequency']}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**Start:** {med['start_date']}")
                if med["end_date"]:
                    st.write(f"**End:** {med['end_date']}")
                if med["instructions"]:
                    st.write(f"**Instructions:** {med['instructions']}")
            with col2:
                if editable:
                    if st.button("🗑️ Deactivate", key=f"deact_{med['id']}"):
                        deactivate_medication(med["id"])
                        st.success(f"{med['name']} deactivated.")
                        st.rerun()

    # Show full history
    with st.expander("📋 All Medications (including inactive)"):
        all_meds = get_medications(patient_id, active_only=False)
        if all_meds:
            import pandas as pd
            df = pd.DataFrame(all_meds)[["name","dosage","unit","frequency","start_date","end_date","is_active"]]
            df.columns = ["Name","Dosage","Unit","Frequency","Start","End","Active"]
            df["Active"] = df["Active"].map({1: "✅", 0: "❌"})
            st.dataframe(df, use_container_width=True)


def render_edit_medication(med_id: int):
    med = get_medication_by_id(med_id)
    if not med:
        st.error("Medication not found.")
        return

    st.subheader(f"✏️ Edit: {med['name']}")
    with st.form(f"edit_med_{med_id}"):
        col1, col2 = st.columns(2)
        with col1:
            name         = st.text_input("Name", value=med["name"])
            dosage       = st.text_input("Dosage", value=med["dosage"])
            unit         = st.selectbox("Unit", UNITS,
                                        index=UNITS.index(med["unit"]) if med["unit"] in UNITS else 0)
            frequency    = st.selectbox("Frequency", FREQUENCIES,
                                        index=FREQUENCIES.index(med["frequency"])
                                        if med["frequency"] in FREQUENCIES else 0)
        with col2:
            instructions = st.text_area("Instructions", value=med["instructions"] or "")
            end_date     = st.text_input("End Date (YYYY-MM-DD)", value=med["end_date"] or "")
            is_active    = st.checkbox("Active", value=bool(med["is_active"]))
        if st.form_submit_button("💾 Update", use_container_width=True):
            update_medication(med_id, name, dosage, unit, frequency,
                              instructions, end_date or None, int(is_active))
            st.success("Medication updated.")
            st.rerun()
