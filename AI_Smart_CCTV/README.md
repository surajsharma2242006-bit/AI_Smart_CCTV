# AI-Powered Smart CCTV & Intruder Detection System

A consent-first Streamlit project for a B.Tech CSE (AI/ML) major project. It supports a locally attached webcam today and compatible IP streams later. It includes YOLO person detection, optional consent-based face matching, motion observations, restricted-zone/prolonged-presence rules, SQLite history, snapshot capture, alert acknowledgement, CSV reports, and optional SMTP delivery.

## Run locally

1. Use Python 3.11–3.13 for the optional `face-recognition` dependency. Python 3.15 can run the rest of the project, while the face module reports that it is unavailable.
2. `cd AI_Smart_CCTV`
3. `python -m venv .venv`
4. Activate it, then run `pip install -r requirements.txt`.
5. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, register an OIDC app with your provider, and add your details. Optionally set `CCTV_ADMIN_EMAILS` to a comma-separated allow-list.
6. Start it: `streamlit run app.py`.

For a **local classroom demonstration only**, set `CCTV_DEMO_MODE=true` before starting. Do not use development mode with a real camera, sensitive imagery, or a network-accessible deployment.

## Privacy and safety notes

- The app does not activate a camera silently; administrators explicitly start and stop it.
- Unknown faces are recorded only as *unrecognized observations*, never automatic intruder determinations.
- Face enrollment requires an affirmative consent checkbox, and the administrator can permanently delete each profile's image and encoding.
- Snapshot deletion is available in Settings. Local files and database are excluded from Git.
- Restrict access to the host, database, snapshots, and OIDC administrator accounts in deployment.

## Optional services

- Store `models/yolo11n.pt` locally for offline YOLO loading.
- For email delivery, set `CCTV_SMTP_HOST`, `CCTV_SMTP_PORT`, `CCTV_SMTP_USERNAME`, `CCTV_SMTP_PASSWORD`, and `CCTV_ALERT_RECIPIENT` in the host environment.
