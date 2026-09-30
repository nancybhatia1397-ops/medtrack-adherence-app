"""
auth.py – Registration, login, session management and care-relationship helpers.
"""
import bcrypt
import streamlit as st
from database import fetchone, execute, fetchall
from config import ROLES


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── User CRUD ─────────────────────────────────────────────────────────────────

def register_user(username: str, password: str, full_name: str,
                  role: str, email: str = "", timezone: str = "UTC") -> tuple[bool, str]:
    if fetchone("SELECT id FROM users WHERE username=?", (username,)):
        return False, "Username already exists."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    hashed = hash_password(password)
    execute(
        "INSERT INTO users (username, password_hash, full_name, role, email, timezone) "
        "VALUES (?,?,?,?,?,?)",
        (username, hashed, full_name, role, email, timezone),
    )
    return True, "Account created successfully."


def login_user(username: str, password: str) -> tuple[bool, str, dict | None]:
    user = fetchone("SELECT * FROM users WHERE username=?", (username,))
    if not user:
        return False, "User not found.", None
    if not verify_password(password, user["password_hash"]):
        return False, "Incorrect password.", None
    return True, "Login successful.", user


def get_user_by_id(user_id: int) -> dict | None:
    return fetchone("SELECT * FROM users WHERE id=?", (user_id,))


def get_all_patients() -> list[dict]:
    return fetchall("SELECT id, username, full_name, email FROM users WHERE role='patient' ORDER BY full_name")


# ── Session state helpers ─────────────────────────────────────────────────────

def set_session(user: dict):
    st.session_state["user"] = user
    st.session_state["user_id"]   = user["id"]
    st.session_state["user_role"] = user["role"]
    st.session_state["user_name"] = user["full_name"]


def clear_session():
    for key in ["user", "user_id", "user_role", "user_name"]:
        st.session_state.pop(key, None)


def is_logged_in() -> bool:
    return "user" in st.session_state


def current_user() -> dict | None:
    return st.session_state.get("user")


def require_login():
    """Redirect to login page if not authenticated (call at top of each page)."""
    if not is_logged_in():
        st.warning("Please log in to continue.")
        st.stop()


# ── Care-relationship helpers ─────────────────────────────────────────────────

def link_patient(caregiver_id: int, patient_id: int) -> tuple[bool, str]:
    existing = fetchone(
        "SELECT id FROM care_relationships WHERE caregiver_id=? AND patient_id=?",
        (caregiver_id, patient_id),
    )
    if existing:
        return False, "Already linked to this patient."
    patient = get_user_by_id(patient_id)
    if not patient or patient["role"] != "patient":
        return False, "Patient not found."
    execute(
        "INSERT INTO care_relationships (caregiver_id, patient_id) VALUES (?,?)",
        (caregiver_id, patient_id),
    )
    return True, f"Linked to patient {patient['full_name']}."


def get_linked_patients(caregiver_id: int) -> list[dict]:
    return fetchall(
        """SELECT u.id, u.username, u.full_name, u.email
           FROM care_relationships cr
           JOIN users u ON u.id = cr.patient_id
           WHERE cr.caregiver_id = ?
           ORDER BY u.full_name""",
        (caregiver_id,),
    )


def unlink_patient(caregiver_id: int, patient_id: int):
    execute(
        "DELETE FROM care_relationships WHERE caregiver_id=? AND patient_id=?",
        (caregiver_id, patient_id),
    )


# ── UI: Login / Register forms ────────────────────────────────────────────────

def render_login_page():
    st.title("💊 MedTrack AI")
    st.caption("AI-Powered Medication Adherence Tracker")
    st.divider()

    tab_login, tab_register = st.tabs(["🔑 Login", "📝 Register"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            ok, msg, user = login_user(username.strip(), password)
            if ok:
                set_session(user)
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with tab_register:
        with st.form("register_form"):
            col1, col2 = st.columns(2)
            with col1:
                r_username  = st.text_input("Username", key="reg_user")
                r_password  = st.text_input("Password", type="password", key="reg_pass")
                r_full_name = st.text_input("Full Name", key="reg_name")
            with col2:
                r_email = st.text_input("Email (optional)", key="reg_email")
                r_role  = st.selectbox("Role", list(ROLES.keys()),
                                       format_func=lambda k: ROLES[k], key="reg_role")
                r_tz    = st.selectbox("Timezone", ["UTC","US/Eastern","US/Central",
                                                    "US/Pacific","Europe/London",
                                                    "Asia/Kolkata","Asia/Tokyo"], key="reg_tz")
            reg_submitted = st.form_submit_button("Create Account", use_container_width=True)
        if reg_submitted:
            ok, msg = register_user(r_username.strip(), r_password,
                                    r_full_name.strip(), r_role,
                                    r_email.strip(), r_tz)
            if ok:
                st.success(msg + " Please log in.")
            else:
                st.error(msg)
