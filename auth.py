"""Login authentication backed by a `users` table. Passwords are bcrypt hashed."""
from __future__ import annotations
import bcrypt
import streamlit as st

import db
import config


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def get_user(username: str):
    df = db.run_query(
        "SELECT id, username, password_hash, full_name, role, is_active "
        "FROM users WHERE username = :u",
        {"u": username},
    )
    return None if df.empty else df.iloc[0].to_dict()


def create_user(username: str, password: str, full_name: str, role: str = "user"):
    db.execute(
        "INSERT INTO users (username, password_hash, full_name, role, is_active) "
        "VALUES (:u, :p, :f, :r, 1)",
        {"u": username.strip(), "p": hash_password(password),
         "f": full_name.strip() or username.strip(), "r": role},
    )


def set_password(username: str, new_password: str):
    db.execute(
        "UPDATE users SET password_hash = :p WHERE username = :u",
        {"p": hash_password(new_password), "u": username.strip()},
    )


def list_users():
    return db.run_query(
        "SELECT id, username, full_name, role, is_active, created_at "
        "FROM users ORDER BY id"
    )


def set_active(username: str, active: bool):
    db.execute("UPDATE users SET is_active = :a WHERE username = :u",
               {"a": 1 if active else 0, "u": username})


def admin_count() -> int:
    df = db.run_query("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND is_active = 1")
    return int(df.iloc[0]["n"])


def update_user(username: str, full_name: str | None = None, role: str | None = None,
                 new_username: str | None = None):
    """Update editable fields for an existing user. Only non-None args are changed."""
    sets, params = [], {"u": username}
    if full_name:
        sets.append("full_name = :f"); params["f"] = full_name.strip()
    if role:
        sets.append("role = :r"); params["r"] = role
    if new_username and new_username.strip() and new_username.strip() != username:
        if get_user(new_username.strip()):
            raise ValueError(f"Username '{new_username}' is already taken.")
        sets.append("username = :nu"); params["nu"] = new_username.strip()
    if not sets:
        return
    db.execute(f"UPDATE users SET {', '.join(sets)} WHERE username = :u", params)


def delete_user(username: str):
    db.execute("DELETE FROM users WHERE username = :u", {"u": username})


# ------------------------------------------------------------------ UI

def _login_form():
    st.title("🌍 " + config.APP_TITLE)
    st.markdown("#### Sign in")

    if not config.credentials_ok():
        st.error(
            "Database credentials are not configured. Copy "
            "`.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, "
            "fill in DB_PASSWORD, and restart the app."
        )
        st.stop()

    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        ok = st.form_submit_button("Sign in", use_container_width=True, type="primary")

    if ok:
        try:
            user = get_user(username.strip())
        except Exception as e:
            st.error(f"Cannot reach the database: {e}")
            return
        if not user or not user.get("is_active") or not verify_password(password, user["password_hash"]):
            st.error("Invalid username or password.")
            return
        st.session_state["user"] = {
            "id": int(user["id"]),
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
        }
        st.rerun()


def require_login():
    """Call at the top of every page."""
    if "user" not in st.session_state:
        _login_form()
        st.stop()
    u = st.session_state["user"]
    st.sidebar.markdown(f"**{u['full_name']}**  \n`{u['role']}`")
    if st.sidebar.button("Log out", use_container_width=True):
        st.session_state.pop("user", None)
        st.rerun()
    return u


def is_admin() -> bool:
    return st.session_state.get("user", {}).get("role") == "admin"
