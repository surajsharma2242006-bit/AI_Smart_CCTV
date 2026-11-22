"""UI renderers shared by the Streamlit pages."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

import cv2
import pandas as pd
import streamlit as st

from alerts import create_security_event
from camera import CameraManager
from config import SNAPSHOTS_DIR, settings
from database import acknowledge_alert, dashboard_metrics, get_alerts, get_events, get_face_profiles
from detector import PersonDetector, point_in_zone
from face_service import erase_face_profile, identify_faces, library_available, register_face
from motion_detection import MotionDetector, PresenceTracker


def initialise_session() -> None:
    if "camera_manager" not in st.session_state:
        st.session_state.camera_manager = CameraManager()
    if "person_detector" not in st.session_state:
        st.session_state.person_detector = PersonDetector()
    if "motion_detector" not in st.session_state:
        st.session_state.motion_detector = MotionDetector(settings.motion_threshold)
    if "presence_tracker" not in st.session_state:
        st.session_state.presence_tracker = PresenceTracker()
    st.session_state.setdefault("camera_active", False)
    st.session_state.setdefault("event_last_logged", {})


def _rate_limited(event_type: str, seconds: int = 30) -> bool:
    previous = st.session_state.event_last_logged.get(event_type)
    if previous and (datetime.now() - previous).total_seconds() < seconds:
        return True
    st.session_state.event_last_logged[event_type] = datetime.now()
    return False


def _zone_values() -> tuple[int, int, int, int]:
    return (
        int(st.session_state.get("zone_x1", 0)), int(st.session_state.get("zone_y1", 0)),
        int(st.session_state.get("zone_x2", 0)), int(st.session_state.get("zone_y2", 0)),
    )


def _draw_zone(frame, zone: tuple[int, int, int, int]):
    x1, y1, x2, y2 = zone
    if x2 > x1 and y2 > y1:
        cv2.rectangle(frame, (x1, y1), (x2, y2), (71, 244, 168), 2)
        cv2.putText(frame, "Restricted zone", (x1 + 6, y1 + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (71, 244, 168), 2)


def _process_frame(frame, detect_people: bool, detect_faces: bool, evaluate_rules: bool, notify: bool):
    annotated = frame.copy()
    people = []
    if detect_people:
        annotated, people = st.session_state.person_detector.detect(frame)
    motion = st.session_state.motion_detector.analyse(frame)
    zone = _zone_values()
    _draw_zone(annotated, zone)
    presence_seconds = st.session_state.presence_tracker.update(len(people))
    face_results = identify_faces(frame) if detect_faces and library_available() else []
    unknown_faces = 0
    for item in face_results:
        top, right, bottom, left = item["location"]
        name = str(item["name"])
        unknown_faces += int(name == "Unknown")
        color = (0, 165, 255) if name == "Unknown" else (34, 197, 94)
        cv2.rectangle(annotated, (left, top), (right, bottom), color, 2)
        cv2.putText(annotated, name, (left, max(20, top - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    if evaluate_rules:
        if zone[2] > zone[0] and zone[3] > zone[1] and any(point_in_zone(person, zone) for person in people):
            if not _rate_limited("Restricted-zone entry"):
                create_security_event("Restricted-zone entry", "High", "A detected person entered the administrator-defined restricted zone.", frame, len(people), notify)
        if presence_seconds >= settings.presence_seconds and not _rate_limited("Prolonged presence", settings.presence_seconds):
            create_security_event("Prolonged presence", "Medium", f"A person has been continuously present for at least {settings.presence_seconds} seconds.", frame, len(people), notify)
        if unknown_faces and not _rate_limited("Unknown face observed"):
            # Observation only: never labels the person an intruder.
            from database import add_event
            add_event("Unknown face observed", "Info", "An unrecognized face was observed. Review context; this is not an intruder determination.", len(people))
    return annotated, people, motion, presence_seconds, unknown_faces


def render_dashboard() -> None:
    st.caption("Security overview for the locally configured camera system.")
    metrics = dashboard_metrics()
    people_now = st.session_state.get("last_people_count", 0)
    with st.container(horizontal=True):
        st.metric("People in latest frame", people_now, border=True)
        st.metric("Registered faces", metrics["registered"], border=True)
        st.metric("Unknown face observations", metrics["unknown"], border=True)
        st.metric("Open security alerts", metrics["open_alerts"], border=True)
        st.metric("Total security events", metrics["events"], border=True)
    status = "Active — camera access is in progress" if st.session_state.camera_active else "Stopped — no camera is being accessed"
    st.info(status, title="Live camera status")
    events = get_events(start=date.today() - timedelta(days=13), end=date.today())
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Detection history")
            if events.empty:
                st.caption("No events yet. Start the camera and configure security rules when ready.")
            else:
                trend = events.assign(day=pd.to_datetime(events["created_at"]).dt.date).groupby("day").size().reset_index(name="Events")
                st.bar_chart(trend, x="day", y="Events", alt="Security events by day")
    with right:
        with st.container(border=True):
            st.subheader("Recent alerts")
            alerts = get_alerts().head(6)
            if alerts.empty:
                st.caption("No alerts recorded.")
            else:
                st.dataframe(alerts[["created_at", "alert_type", "severity", "acknowledged"]], hide_index=True, alt="Six most recent security alerts")


def render_live_camera() -> None:
    st.caption("Camera access starts only after you press Start. A green indicator remains visible while it is active.")
    if settings.hosted_deployment:
        st.warning(
            "Live server-camera monitoring is disabled for this hosted deployment. "
            "Use Person detection to capture a one-time image in your browser, or run this app on the camera host.",
            title="Hosted deployment limitation",
        )
        return
    source_kind = st.segmented_control("Camera source", ["Laptop webcam", "IP camera"], default="Laptop webcam", key="source_kind")
    source = 0
    if source_kind == "IP camera":
        source = st.text_input("Compatible IP stream URL", placeholder="rtsp://user:password@camera/stream", key="ip_camera_url")
    c1, c2, c3 = st.columns([1, 1, 2], vertical_alignment="bottom")
    with c1:
        if st.button("Start camera", icon=":material/videocam:", width="stretch"):
            if source_kind == "IP camera" and not source:
                st.error("Enter the IP camera stream URL first.")
            else:
                ok, message = st.session_state.camera_manager.start(source)
                st.session_state.camera_active = ok
                (st.success if ok else st.error)(message)
    with c2:
        if st.button("Stop camera", icon=":material/videocam_off:", width="stretch"):
            st.session_state.camera_manager.stop()
            st.session_state.camera_active = False
            st.info("Camera stopped. No further frames are read.")
    with c3:
        st.toggle("Evaluate configured security rules", key="rules_enabled", value=True)
    st.toggle(
        "Send configured email alerts for security-rule events",
        key="notify_emails",
        value=False,
        disabled=not settings.email_ready,
        help="Enabled only when SMTP environment variables are configured.",
    )

    if st.session_state.camera_active:
        st.success("RECORDING INDICATOR: camera is active and frames are processed locally.", icon=":material/fiber_manual_record:")
        st.caption("Use Refresh frame for a controlled, on-demand preview. This avoids hidden background recording.")
        enable_faces = st.toggle("Run face matching for this preview", value=False, help="Only registered, consented face profiles are compared.")
        if st.button("Refresh frame", icon=":material/refresh:", width="content"):
            frame = st.session_state.camera_manager.read()
            if frame is None:
                st.error("No frame received. Check the camera and restart it.")
            else:
                annotated, people, motion, presence, unknown = _process_frame(
                    frame, True, enable_faces, st.session_state.rules_enabled, st.session_state.notify_emails
                )
                st.session_state.last_people_count = len(people)
                st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), alt="Latest annotated camera frame")
                a, b, c, d = st.columns(4)
                a.metric("People", len(people))
                b.metric("Motion", "Observed" if motion.motion_detected else "Not observed")
                c.metric("Presence", f"{presence}s")
                d.metric("Unknown faces", unknown)
    else:
        st.info("No feed is open. Starting the camera is an explicit administrator action.")


def render_person_detection() -> None:
    st.caption("YOLO detects people only; confidence and bounding boxes are shown on processed frames.")
    detector = st.session_state.person_detector
    if detector.model is None:
        st.warning("YOLO loads on the first frame. Place `yolo11n.pt` in `models/` for offline use, or let Ultralytics obtain it during initial setup.")
    confidence = st.slider("Minimum person confidence", 0.10, 0.95, 0.45, 0.05)
    detector.confidence = confidence
    photo = st.camera_input("Take a one-time test image", help="This is an explicit capture; it does not start continuous monitoring.")
    if photo:
        file_bytes = photo.getvalue()
        frame = cv2.imdecode(__import__("numpy").frombuffer(file_bytes, __import__("numpy").uint8), cv2.IMREAD_COLOR)
        annotated, people = detector.detect(frame)
        st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), alt="Test image annotated with detected people")
        st.metric("Detected people", len(people))
        if detector.error:
            st.error(detector.error)


def render_face_registration() -> None:
    st.caption("Register a face only after the person has given informed consent. Unknown means unrecognized — never an intruder verdict.")
    if not library_available():
        st.warning("Optional face-recognition support is not available in this Python environment. You can still use camera, YOLO, motion, alerts, and reports.")
    with st.form("face_registration"):
        name = st.text_input("Authorized person’s display name", max_chars=60)
        consent = st.checkbox("I confirm this person has consented to face registration and understands the local storage purpose.")
        image = st.camera_input("Capture consented registration photo")
        submitted = st.form_submit_button("Register consented face", icon=":material/person_add:")
    if submitted:
        if not consent:
            st.error("Face registration requires affirmative consent.")
        elif not image:
            st.error("Capture a clear photo first.")
        else:
            ok, message = register_face(name, image.getvalue())
            (st.success if ok else st.error)(message)
    profiles = get_face_profiles()
    st.subheader("Registered face data")
    if profiles.empty:
        st.caption("No active consented profiles.")
    else:
        st.dataframe(profiles[["id", "display_name", "consent_at"]], hide_index=True, alt="Active consented face profiles")
        profile_id = st.selectbox("Profile to delete", profiles["id"].tolist(), format_func=lambda identifier: profiles.loc[profiles.id == identifier, "display_name"].iloc[0])
        confirm = st.checkbox("I understand this permanently deletes the stored registration image and encoding.", key="confirm_face_delete")
        if st.button("Delete selected face data", type="secondary", icon=":material/delete:"):
            if not confirm:
                st.error("Confirm permanent deletion first.")
            elif erase_face_profile(int(profile_id)):
                st.success("Stored face image and encoding deleted.")
                st.rerun()


def render_security_alerts() -> None:
    st.caption("Alerts are created by configured rule violations. Motion alone is an observation, not a confirmed security incident.")
    alerts = get_alerts()
    if alerts.empty:
        st.info("No security alerts to review.")
        return
    for row in alerts.head(20).itertuples():
        title = f"{row.severity} · {row.alert_type} · {row.created_at}"
        with st.expander(title, expanded=not bool(row.acknowledged)):
            st.write(row.message)
            if row.snapshot_path and Path(row.snapshot_path).exists():
                st.image(row.snapshot_path, alt=f"Snapshot for {row.alert_type}")
            if row.acknowledged:
                st.caption(f"Acknowledged at {row.acknowledged_at}")
            elif st.button("Acknowledge alert", key=f"ack_{row.id}", icon=":material/done:"):
                acknowledge_alert(int(row.id))
                st.rerun()


def render_event_history() -> None:
    st.caption("Search the locally stored event history. Snapshot access is restricted to authenticated administrators.")
    first, second, third = st.columns(3)
    with first:
        start = st.date_input("From", value=date.today() - timedelta(days=30))
    with second:
        end = st.date_input("To", value=date.today())
    available = get_events()
    event_types = ["All"] + sorted(available["event_type"].unique().tolist()) if not available.empty else ["All"]
    with third:
        event_type = st.selectbox("Event type", event_types)
    events = get_events(start, end, event_type)
    if events.empty:
        st.info("No events match these filters.")
        return
    display = events[["id", "created_at", "event_type", "severity", "message", "people_count", "snapshot_path"]]
    st.dataframe(display, hide_index=True, alt="Filtered security event history")
    snapshot_events = events[events["snapshot_path"].notna()]
    if not snapshot_events.empty:
        selected_id = st.selectbox("View a captured snapshot", snapshot_events["id"].tolist())
        selection = snapshot_events.loc[snapshot_events.id == selected_id].iloc[0]
        if Path(selection.snapshot_path).exists():
            st.image(selection.snapshot_path, alt=f"Snapshot for event {selected_id}")


def render_reports() -> None:
    st.caption("Generate a CSV report from the filtered local event database.")
    period = st.selectbox("Report period", ["Last 7 days", "Last 30 days", "All time"])
    start = {"Last 7 days": date.today() - timedelta(days=7), "Last 30 days": date.today() - timedelta(days=30)}.get(period)
    events = get_events(start=start, end=date.today())
    if events.empty:
        st.info("No event data is available for this report period.")
        return
    summary = events.groupby(["event_type", "severity"]).size().reset_index(name="Count")
    st.bar_chart(summary, x="event_type", y="Count", color="severity", alt="Security event counts by type and severity")
    st.dataframe(summary, hide_index=True, alt="Security event report summary")
    csv = events.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV report", csv, "smart_cctv_event_report.csv", "text/csv", icon=":material/download:")


def render_settings() -> None:
    st.caption("Configure rule boundaries and review privacy controls. Keep SMTP credentials in environment variables or Streamlit secrets, never in this screen.")
    st.subheader("Restricted zone")
    st.caption("Coordinates use the camera frame’s pixel coordinate system: x1, y1 (top-left) and x2, y2 (bottom-right). Leave zeroed to disable the zone.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.number_input("x1", min_value=0, value=int(st.session_state.get("zone_x1", 0)), key="zone_x1")
    with c2:
        st.number_input("y1", min_value=0, value=int(st.session_state.get("zone_y1", 0)), key="zone_y1")
    with c3:
        st.number_input("x2", min_value=0, value=int(st.session_state.get("zone_x2", 0)), key="zone_x2")
    with c4:
        st.number_input("y2", min_value=0, value=int(st.session_state.get("zone_y2", 0)), key="zone_y2")
    st.subheader("Alert delivery")
    st.table({"SMTP status": "Configured" if settings.email_ready else "Not configured", "Snapshot cooldown": f"{settings.snapshot_cooldown_seconds} seconds", "Prolonged presence rule": f"{settings.presence_seconds} seconds"}, border="horizontal", width="content", alt="Alert and retention configuration")
    if not settings.email_ready:
        st.info("To enable optional email, set CCTV_SMTP_HOST, CCTV_SMTP_PORT, CCTV_SMTP_USERNAME, CCTV_SMTP_PASSWORD, and CCTV_ALERT_RECIPIENT in the deployment environment.")
    if settings.hosted_deployment:
        st.warning(
            "This instance uses the hosted-deployment mode. Streamlit Community Cloud storage is temporary; "
            "connect persistent storage before using it for security records or consented face data.",
            title="Storage warning",
        )
    st.subheader("Snapshot privacy")
    files = sorted(SNAPSHOTS_DIR.glob("*.jpg"))
    st.write(f"Stored snapshots: {len(files)}")
    confirm = st.checkbox("I understand this permanently deletes all local snapshots.", key="confirm_snapshot_delete")
    if st.button("Delete all snapshots", type="secondary", icon=":material/delete_sweep:"):
        if not confirm:
            st.error("Confirm permanent deletion first.")
        else:
            for snapshot in files:
                snapshot.unlink(missing_ok=True)
            st.success("All stored snapshots were deleted. Event records remain, with missing snapshot links.")
