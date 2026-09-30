"""
ai_insights.py – Gemini 2.5 Flash integration for AI-powered adherence analysis.
"""
import streamlit as st
import google.generativeai as genai
from datetime import datetime
from database import execute, fetchall
from adherence import (
    get_logs_dataframe,
    compute_adherence_rate,
    compute_per_medication_rates,
    compute_streak,
)
from config import GEMINI_API_KEY, GEMINI_MODEL


# ── Gemini client ─────────────────────────────────────────────────────────────

def _get_model():
    if not GEMINI_API_KEY:
        return None
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(GEMINI_MODEL)


# ── Context builder ───────────────────────────────────────────────────────────

def _build_patient_context(patient_id: int, days: int = 30) -> str:
    rate    = compute_adherence_rate(patient_id, days)
    streak  = compute_streak(patient_id)
    per_med = compute_per_medication_rates(patient_id, days)
    df      = get_logs_dataframe(patient_id, days)

    lines = [
        f"Patient adherence summary (last {days} days):",
        f"- Overall adherence rate: {rate}%",
        f"- Current consecutive-day streak: {streak} day(s)",
        "",
        "Per-medication breakdown:",
    ]

    if per_med.empty:
        lines.append("  (no data)")
    else:
        for _, row in per_med.iterrows():
            lines.append(
                f"  • {row['Medication']}: {row['Taken']} taken, "
                f"{row['Missed']} missed, {row['Skipped']} skipped "
                f"→ {row['Rate (%)']}%"
            )

    if not df.empty and "status" in df.columns:
        missed_recent = df[df["status"] == "missed"].head(5)
        if not missed_recent.empty:
            lines.append("")
            lines.append("Most recent missed doses:")
            for _, r in missed_recent.iterrows():
                lines.append(f"  • {r['med_name']} on {r['scheduled_for'][:10]}")

    return "\n".join(lines)


# ── Core AI call ──────────────────────────────────────────────────────────────

def generate_insight(patient_id: int, custom_question: str = "", days: int = 30) -> str:
    model = _get_model()
    if model is None:
        return "⚠️ Gemini API key not configured. Add GEMINI_API_KEY to your .env file."

    context = _build_patient_context(patient_id, days)

    if custom_question.strip():
        prompt = f"""{context}

Patient / caregiver question: {custom_question}

You are a helpful medical AI assistant. Based solely on the adherence data above,
provide a concise, empathetic, and actionable response. Do NOT invent clinical
advice beyond what the data supports. Always recommend consulting a doctor for
medical decisions."""
    else:
        prompt = f"""{context}

You are a helpful medical AI assistant. Analyse the medication adherence data above
and provide:
1. A brief overall assessment (1–2 sentences).
2. Any concerning patterns you notice (missed streaks, specific medications with low adherence).
3. 2–3 practical, empathetic suggestions to improve adherence.
4. A motivational closing sentence.

Keep the response concise (under 300 words). Use plain language — the reader may be a patient or caregiver."""

    try:
        response = model.generate_content(prompt)
        insight  = response.text.strip()
        # Persist to DB
        execute(
            "INSERT INTO ai_insights (patient_id, insight) VALUES (?,?)",
            (patient_id, insight),
        )
        return insight
    except Exception as exc:
        return f"⚠️ AI error: {exc}"


# ── Streamlit UI ──────────────────────────────────────────────────────────────

def render_ai_insights(patient_id: int):
    st.subheader("🤖 AI-Powered Insights")

    if not GEMINI_API_KEY:
        st.error(
            "Gemini API key not found. Please add `GEMINI_API_KEY=<your-key>` "
            "to a `.env` file in the project root."
        )
        return

    days = st.slider("Analyse the last N days", 7, 90, 30, key="ai_days")

    col1, col2 = st.columns([3, 1])
    with col1:
        custom_q = st.text_input(
            "Ask a specific question (optional)",
            placeholder="e.g. Why am I missing evening doses?",
        )
    with col2:
        st.write("")
        st.write("")
        run = st.button("✨ Generate Insight", use_container_width=True)

    if run:
        with st.spinner("Analysing with Gemini 2.5 Flash…"):
            insight = generate_insight(patient_id, custom_q, days)
        st.markdown("---")
        st.markdown(insight)
        st.caption(f"Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")

    # Show past insights
    past = fetchall(
        "SELECT insight, created_at FROM ai_insights WHERE patient_id=? ORDER BY created_at DESC LIMIT 5",
        (patient_id,),
    )
    if past:
        with st.expander("📜 Previous AI Insights"):
            for p in past:
                st.caption(p["created_at"])
                st.markdown(p["insight"])
                st.divider()


def render_ai_chat(patient_id: int):
    """Interactive multi-turn AI chat for the patient/caregiver."""
    st.subheader("💬 Chat with MedTrack AI")

    if not GEMINI_API_KEY:
        st.error("Gemini API key not configured.")
        return

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Display prior messages
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # New message
    user_input = st.chat_input("Ask MedTrack AI about your medication…")
    if user_input:
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        context = _build_patient_context(patient_id, days=30)
        system_prompt = (
            "You are MedTrack AI, an empathetic medication adherence assistant. "
            "You have access to the patient's adherence data. "
            "Answer the user's question based on this data and general health knowledge. "
            "Always recommend consulting a doctor for clinical decisions.\n\n"
            + context
        )

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in st.session_state["chat_history"][:-1]
        )
        full_prompt = f"{system_prompt}\n\nConversation so far:\n{history_text}\n\nUSER: {user_input}\nASSISTANT:"

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    model    = _get_model()
                    response = model.generate_content(full_prompt)
                    reply    = response.text.strip()
                except Exception as exc:
                    reply = f"⚠️ Error: {exc}"
                st.markdown(reply)

        st.session_state["chat_history"].append({"role": "assistant", "content": reply})

    if st.session_state["chat_history"]:
        if st.button("🗑️ Clear Chat"):
            st.session_state["chat_history"] = []
            st.rerun()
