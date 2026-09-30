"""
dashboard.py – Plotly charts and analytics views for patients, caregivers & doctors.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from adherence import (
    compute_adherence_rate,
    compute_per_medication_rates,
    compute_streak,
    get_logs_dataframe,
    adherence_badge,
)
from auth import get_linked_patients, get_user_by_id
from medications import get_medications
from config import ADHERENCE_EXCELLENT, ADHERENCE_GOOD, ADHERENCE_POOR


# ── Metric cards ──────────────────────────────────────────────────────────────

def render_metric_cards(patient_id: int, days: int = 30):
    rate   = compute_adherence_rate(patient_id, days)
    streak = compute_streak(patient_id)
    meds   = get_medications(patient_id, active_only=True)
    df     = get_logs_dataframe(patient_id, days)
    missed = len(df[df["status"] == "missed"]) if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Adherence Rate", f"{rate}%",
              delta="Excellent" if rate >= ADHERENCE_EXCELLENT else
                    "Good"      if rate >= ADHERENCE_GOOD      else "Needs attention")
    c2.metric("🔥 Streak", f"{streak} day(s)")
    c3.metric("💊 Active Meds", len(meds))
    c4.metric("❌ Missed Doses", missed, delta=f"last {days}d", delta_color="inverse")


# ── Adherence over time line chart ────────────────────────────────────────────

def render_adherence_timeline(patient_id: int, days: int = 30):
    df = get_logs_dataframe(patient_id, days)
    if df.empty:
        st.info("No data yet — start logging doses to see the timeline.")
        return

    df["day"]    = pd.to_datetime(df["scheduled_for"]).dt.date
    daily        = df.groupby(["day", "status"]).size().unstack(fill_value=0)

    for col in ["taken", "missed", "skipped"]:
        if col not in daily.columns:
            daily[col] = 0

    daily["rate"] = (daily["taken"] / (daily["taken"] + daily["missed"]).replace(0, 1) * 100).round(1)
    daily         = daily.reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["day"], y=daily["rate"],
        mode="lines+markers", name="Adherence %",
        line=dict(color="#3b82d4", width=2),
        marker=dict(size=6),
    ))
    fig.add_hline(y=ADHERENCE_EXCELLENT, line_dash="dash", line_color="green",
                  annotation_text="Excellent", annotation_position="bottom right")
    fig.add_hline(y=ADHERENCE_GOOD, line_dash="dash", line_color="orange",
                  annotation_text="Good",      annotation_position="bottom right")
    fig.update_layout(
        title="Daily Adherence Rate (%)",
        xaxis_title="Date", yaxis_title="Adherence %",
        yaxis=dict(range=[0, 105]),
        plot_bgcolor="white",
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Per-medication bar chart ──────────────────────────────────────────────────

def render_per_medication_chart(patient_id: int, days: int = 30):
    df = compute_per_medication_rates(patient_id, days)
    if df.empty:
        return

    fig = px.bar(
        df, x="Medication", y=["Taken", "Missed", "Skipped"],
        barmode="group",
        color_discrete_map={"Taken": "#22c55e", "Missed": "#ef4444", "Skipped": "#f59e0b"},
        title="Doses per Medication",
        height=350,
    )
    fig.update_layout(plot_bgcolor="white", legend_title_text="Status")
    st.plotly_chart(fig, use_container_width=True)


# ── Adherence rate per medication ─────────────────────────────────────────────

def render_adherence_rate_chart(patient_id: int, days: int = 30):
    df = compute_per_medication_rates(patient_id, days)
    if df.empty:
        return

    colors = [
        "#22c55e" if r >= ADHERENCE_EXCELLENT else
        "#f59e0b" if r >= ADHERENCE_GOOD else
        "#ef4444"
        for r in df["Rate (%)"]
    ]
    fig = go.Figure(go.Bar(
        x=df["Medication"], y=df["Rate (%)"],
        marker_color=colors,
        text=df["Rate (%)"].astype(str) + "%",
        textposition="outside",
    ))
    fig.update_layout(
        title="Adherence Rate by Medication (%)",
        yaxis=dict(range=[0, 110]),
        plot_bgcolor="white",
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Heatmap: dose status calendar ────────────────────────────────────────────

def render_heatmap(patient_id: int, days: int = 60):
    df = get_logs_dataframe(patient_id, days)
    if df.empty:
        return

    df["day"] = pd.to_datetime(df["scheduled_for"]).dt.date
    daily     = df.groupby("day")["status"].apply(
        lambda s: 1 if (s == "taken").any() else (-1 if (s == "missed").any() else 0)
    ).reset_index()
    daily.columns = ["day", "value"]
    daily["day"]  = pd.to_datetime(daily["day"])
    daily["week"] = daily["day"].dt.isocalendar().week
    daily["dow"]  = daily["day"].dt.dayofweek

    color_map = {1: "green", 0: "lightgray", -1: "red"}
    label_map = {1: "Taken", 0: "Skipped", -1: "Missed"}

    fig = px.scatter(
        daily, x="week", y="dow",
        color="value",
        color_discrete_map={1: "#22c55e", 0: "#d1d5db", -1: "#ef4444"},
        symbol="value",
        hover_data={"day": True, "value": False},
        title="Dose Calendar (last 60 days)",
        height=300,
    )
    fig.update_traces(marker_size=14)
    fig.update_layout(
        yaxis=dict(tickvals=list(range(7)),
                   ticktext=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]),
        xaxis_title="Week", yaxis_title="Day",
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Patient-level dashboard ───────────────────────────────────────────────────

def render_patient_dashboard(patient_id: int):
    st.subheader("📈 My Adherence Dashboard")
    days = st.select_slider("Period", options=[7, 14, 30, 60, 90], value=30)

    render_metric_cards(patient_id, days)
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        render_adherence_timeline(patient_id, days)
    with col2:
        render_adherence_rate_chart(patient_id, days)

    render_per_medication_chart(patient_id, days)
    render_heatmap(patient_id, 60)


# ── Caregiver / Doctor multi-patient overview ─────────────────────────────────

def render_caregiver_overview(caregiver_id: int):
    st.subheader("👥 Patient Monitoring Overview")

    patients = get_linked_patients(caregiver_id)
    if not patients:
        st.info("No patients linked yet. Use the **Patients** tab to link patients.")
        return

    # Summary table
    rows = []
    for p in patients:
        rate   = compute_adherence_rate(p["id"], 30)
        streak = compute_streak(p["id"])
        meds   = len(get_medications(p["id"], active_only=True))
        rows.append({
            "Patient":    p["full_name"],
            "Username":   p["username"],
            "Meds":       meds,
            "Adherence":  f"{rate}%",
            "Streak":     f"{streak}d",
            "Status":     adherence_badge(rate),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    # Drill into a specific patient
    st.markdown("---")
    st.markdown("##### Drill Into a Patient")
    selected_name = st.selectbox("Select Patient", [p["full_name"] for p in patients])
    sel_patient   = next(p for p in patients if p["full_name"] == selected_name)

    days = st.select_slider("Period", options=[7, 14, 30, 60, 90], value=30, key="cg_days")

    render_metric_cards(sel_patient["id"], days)
    st.markdown("---")
    render_adherence_timeline(sel_patient["id"], days)
    render_per_medication_chart(sel_patient["id"], days)


# ── Manage patients panel (link / unlink) ─────────────────────────────────────

def render_manage_patients(caregiver_id: int):
    from auth import link_patient, unlink_patient, get_all_patients
    st.subheader("🔗 Manage Linked Patients")

    all_patients  = get_all_patients()
    linked        = get_linked_patients(caregiver_id)
    linked_ids    = {p["id"] for p in linked}

    unlinked = [p for p in all_patients if p["id"] not in linked_ids]

    # Link
    if unlinked:
        st.markdown("##### Link a New Patient")
        names = {f"{p['full_name']} (@{p['username']})": p["id"] for p in unlinked}
        sel   = st.selectbox("Patient to link", list(names.keys()), key="link_sel")
        if st.button("🔗 Link Patient"):
            ok, msg = link_patient(caregiver_id, names[sel])
            (st.success if ok else st.error)(msg)
            st.rerun()
    else:
        st.info("All registered patients are already linked.")

    # Unlink
    if linked:
        st.markdown("##### Linked Patients")
        for p in linked:
            c1, c2 = st.columns([4, 1])
            c1.write(f"👤 **{p['full_name']}** (@{p['username']})")
            if c2.button("Unlink", key=f"unlink_{p['id']}"):
                unlink_patient(caregiver_id, p["id"])
                st.rerun()
