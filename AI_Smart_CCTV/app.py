"""AI-Powered Smart CCTV & Intruder Detection System entry point."""
from __future__ import annotations

import os

import streamlit as st

from database import initialise_database
from views import initialise_session


st.set_page_config(page_title="Smart CCTV", page_icon=":material/shield:", layout="wide")
initialise_database()
initialise_session()


def auth_ready() -> bool:
    try:
        return bool(st.secrets.get("auth"))
    except Exception:
        return False


def require_administrator() -> None:
    # An explicit local development opt-in keeps classroom demonstrations possible
    # without weakening production's real OIDC authentication requirement.
    if os.getenv("CCTV_DEMO_MODE", "false").lower() == "true":
        st.sidebar.warning("Development demonstration mode: do not use with a real camera or sensitive data.")
        return
    if not auth_ready():
        st.title("Administrator authentication required", icon=":material/lock:")
        st.error("This application is locked until an OpenID Connect administrator identity provider is configured.")
        st.code(
            "[auth]\nredirect_uri = \"http://localhost:8501/oauth2callback\"\n"
            "cookie_secret = \"generate-a-long-random-value\"\n"
            "client_id = \"provider-client-id\"\nclient_secret = \"provider-client-secret\"\n"
            "server_metadata_url = \"https://provider/.well-known/openid-configuration\"",
            language="toml",
        )
        st.caption("Save this as `.streamlit/secrets.toml` (never commit it), register the redirect URI with your identity provider, then restart the app.")
        st.stop()
    if not st.user.is_logged_in:
        st.title("Administrator sign in", icon=":material/admin_panel_settings:")
        if st.button("Sign in with your identity provider", icon=":material/login:"):
            st.login()
        st.stop()
    admin_emails = [email.strip().lower() for email in os.getenv("CCTV_ADMIN_EMAILS", "").split(",") if email.strip()]
    if admin_emails and str(st.user.email).lower() not in admin_emails:
        st.error("Your signed-in account is not an authorized CCTV administrator.")
        st.stop()


require_administrator()

pages = {
    "Monitor": [
        st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", help="Security overview with camera state, metrics, alerts, and detection trends."),
        st.Page("app_pages/live_camera.py", title="Live camera", icon=":material/videocam:", help="Explicitly start and stop a laptop webcam or compatible IP stream."),
        st.Page("app_pages/person_detection.py", title="Person detection", icon=":material/person_search:", help="Run YOLO person detection and inspect confidence-labelled bounding boxes."),
    ],
    "Security": [
        st.Page("app_pages/face_registration.py", title="Face registration", icon=":material/face:", help="Register and delete consented face profiles; unknown never means intruder."),
        st.Page("app_pages/security_alerts.py", title="Security alerts", icon=":material/notification_important:", help="Review event-based alerts, snapshots, and acknowledgement state."),
        st.Page("app_pages/event_history.py", title="Event history", icon=":material/history:", help="Filter locally stored security events and securely view linked snapshots."),
    ],
    "Administration": [
        st.Page("app_pages/reports.py", title="Reports", icon=":material/assessment:", help="Summarize stored events and export a CSV report."),
        st.Page("app_pages/settings.py", title="Settings", icon=":material/settings:", help="Set restricted-zone coordinates and manage privacy-related stored data."),
    ],
}

with st.sidebar:
    st.title("Smart CCTV", icon=":material/shield:")
    st.caption("Consent-first security monitoring")
    if os.getenv("CCTV_DEMO_MODE", "false").lower() != "true":
        st.caption(f"Signed in as {st.user.name}")
        if st.button("Log out", icon=":material/logout:", width="stretch"):
            st.logout()

page = st.navigation(pages, position="sidebar")
st.title(page.title, icon=page.icon)
page.run()
