# AI-Powered Smart CCTV & Intruder Detection System

A consent-first Streamlit project for a B.Tech CSE (AI/ML) major project. It supports a locally attached webcam today and compatible IP streams later. It includes YOLO person detection, optional consent-based face matching, motion observations, restricted-zone/prolonged-presence rules, SQLite history, snapshot capture, alert acknowledgement, CSV reports, and optional SMTP delivery.

## Deploy to Streamlit Community Cloud

The app is ready to deploy from the `AI_Smart_CCTV` folder.

1. Push this project to GitHub.
2. In [Streamlit Community Cloud](https://share.streamlit.io/), create an app from the repository and select `AI_Smart_CCTV/app.py` as the main file.
3. Add the contents of `.streamlit/secrets.toml.example` in **Advanced settings → Secrets**. Replace every placeholder and set `redirect_uri` to `https://<your-app>.streamlit.app/oauth2callback` before registering that same URI with the identity provider.
4. Add `CCTV_HOSTED_DEPLOYMENT = "true"` to the secrets. This disables the server-camera page, because a hosted server cannot access a visitor's laptop webcam.
5. Deploy. The **Person detection** page still supports explicit browser camera captures.

`requirements.txt`, `.streamlit/config.toml`, and `runtime.txt` are in the app folder. The requirements install Streamlit's authentication extra needed for OIDC sign-in. The repository-root `packages.txt` installs the Linux system libraries required by OpenCV. Face matching is deliberately optional in hosted deployments: its native `dlib` dependency is unreliable on managed builders, while camera-input detection, motion analysis, alerts, reports, and the consent workflow remain available.

### Important hosted-service limits

- Streamlit Community Cloud has temporary local disk. Events, snapshots, and enrolled faces can disappear when the container restarts. Do not use it as production CCTV evidence storage. Set `CCTV_DATA_DIR` only on a self-hosted deployment with a persistent mounted volume.
- The live camera/RTSP workflow must run on a machine that can reach the camera. For a production system, host the app or a separate camera agent on that private network.
- Keep all real credentials in Streamlit secrets or host environment variables; never commit `.streamlit/secrets.toml`.

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
- To enable consented face matching locally, install its optional native dependencies separately: `pip install face-recognition face-recognition-models dlib-bin`. It is intentionally not included in the managed-cloud dependency set.
