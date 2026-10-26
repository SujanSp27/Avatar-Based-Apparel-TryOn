# VastraView: AI-Powered Virtual Try-On & Body Anthropometry Studio

[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162.0-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.1.0-61DAFB.svg?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.8.3-3178C6.svg?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.4.4-646CFF.svg?style=flat&logo=vite&logoColor=white)](https://vitejs.dev/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Tasks%20Pose-00A4E4.svg?style=flat&logo=google&logoColor=white)](https://developers.google.com/mediapipe)
[![Model](https://img.shields.io/badge/VTON-FASHN%201.5%20(Colab%20GPU)-FF6F00.svg?style=flat&logo=googlecolab&logoColor=white)](https://colab.research.google.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Community%208.2-47A248.svg?style=flat&logo=mongodb&logoColor=white)](https://www.mongodb.com/)

**VastraView** is a full-stack, privacy-first virtual fitting room and body anthropometry platform. It delivers photorealistic 2D garment virtual try-on powered by **FASHN VTON 1.5** running seamlessly on the user's private Google Colab GPU (NVIDIA T4 or better), paired with real-time CPU-based 33-point body landmark measurement extraction and independent brand sizing recommendations.

The platform eliminates expensive local GPU requirements and third-party SaaS API subscriptions by utilizing an automated self-healing Colab bridge, while enforcing semantic preservation to preserve faces, hands, skin tones, and backgrounds.

---

## 📑 Table of Contents

- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Project Directory Structure](#-project-directory-structure)
- [Prerequisites](#-prerequisites)
- [Quick Start Guide (Windows)](#-quick-start-guide-windows)
- [Google Colab GPU Worker Setup](#-google-colab-gpu-worker-setup)
- [Core Workflows](#-core-workflows)
  - [1. 2D Photo Virtual Try-On](#1-2d-photo-virtual-try-on)
  - [2. CPU Body Measurement & Anthropometry](#2-cpu-body-measurement--anthropometry)
  - [3. Intelligent Brand Size Recommendation](#3-intelligent-brand-size-recommendation)
- [API Reference](#-api-reference)
- [Environment Configuration](#-environment-configuration)
- [Testing & Quality Assurance](#-testing--quality-assurance)
- [Security & Privacy](#-security--privacy)
- [Detailed Documentation Index](#-detailed-documentation-index)
- [Troubleshooting & FAQ](#-troubleshooting--faq)

---

## 🌟 Key Features

### 1. 2D Photorealistic Virtual Try-On
- **Private Colab Worker Engine**: Executes official **FASHN VTON 1.5** inference remotely on free-tier or Pro Google Colab GPUs (NVIDIA T4/A100) via an encrypted, self-recovering reverse tunnel.
- **11 Garment Categories**: Supports Tops (*T-shirt, shirt, blouse, sweater, jacket*), Bottoms (*trousers, jeans, shorts, skirt*), and One-pieces (*dress, jumpsuit*).
- **Dual Photo Inputs**: Works with both product flat-lays (ghost mannequin / isolated e-commerce cuts) and photos worn by models.
- **Semantic Preservation & Lossless Patching**: Preserves the user's face, neck, arms, and original background with pixel-identical fidelity; only clothing regions are synthesized.
- **Quality Gates**: Automatically rejects invalid inferences (e.g., severe limb occlusion or generations that leave >20% unresolved exposed skin).

### 2. High-Precision Anthropometry (Local CPU)
- **MediaPipe Tasks Pose Landmarker Full**: Fast, zero-GPU body landmark extraction on local CPU.
- **33 Keypoints Analyzed**: Evaluates 3D landmark coordinates and visibility scores (>0.65 threshold).
- **6 Extracted Metrics**: Height-calibrated extraction of **Shoulder Width**, **Chest Circumference**, **Waist Circumference**, **Hip Circumference**, **Thigh Circumference**, and **Inseam**.
- **Interactive Landmark Canvas**: Live overlay displaying detected skeleton, bounding silhouettes, and GrabCut segmentation masks on the uploaded user photo.

### 3. Sourced Brand Sizing Engine
- **23 Official Chart Scopes**: Real measurement charts for major apparel brands including **Nike India**, **Puma India**, **Levi's**, **Manyavar**, **Adidas**, and **H&M**.
- **Dual Scoring Mechanisms**:
  - *MongoDB V1 API*: Exact midpoint-relative Euclidean distance formula for fine-grained metric matching.
  - *PostgreSQL Legacy API*: Interval-distance scoring with customizable ease preferences (*Tight, Regular, Loose*).
- **Dimension Fit Breakdown**: Metric-by-metric fit feedback (e.g., "Waist: Snug", "Chest: Ideal") to eliminate online shopping sizing uncertainty.

### 4. Modern Fashion Studio Web App
- Built with **React 19**, **TypeScript**, **Vite**, and custom **Cream/Sage** editorial design system.
- Interactive side-by-side and split-screen comparison slider with high-resolution pan/zoom.
- Camera capture mode with pose-alignment silhouettes for instant photo measurements.
- Curated reference wardrobe with 57 built-in garment assets, private scan history, favorites, and "My Closet".

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph Client["Frontend Studio (React 19 + TypeScript + Vite)"]
        UI["Modern Fashion UI (Port 5173)"]
        Canvas["Interactive Landmark Canvas"]
        Slider["Before / After Result Comparison"]
    end

    subgraph Backend["Core API Service (FastAPI / Uvicorn - Port 8000)"]
        Router["FastAPI Application Gateway"]
        Auth["Argon2id Auth & Session Manager"]
        JobQueue["Asynchronous Try-On Job Manager (.runtime/tryon-jobs)"]
        ColabBridge["Automated Colab Connection Monitor"]
        Anthro["Anthropometry Engine (MediaPipe Pose CPU + GrabCut)"]
        Sizing["Sizing Recommendation Engine"]
    end

    subgraph Databases["Local Data Layer"]
        PG[("PostgreSQL 17\nPort 5433\nRuns & Legacy Charts")]
        Mongo[("MongoDB Community 8.2\nPort 27018\nAccounts, Scans & Brand Charts")]
        Storage[("Local Asset Store\n/data/processed")]
    end

    subgraph Remote["Private Cloud Compute (Google Colab GPU)"]
        Tunnel["Encrypted Reverse HTTPS Tunnel"]
        Worker["Colab Worker (online_worker.py)"]
        VTON["FASHN VTON 1.5 PyTorch Model (FP16 / CUDA T4)"]
    end

    UI <-->|REST API + JWT / HttpOnly Cookie| Router
    Canvas <-->|Landmark Coordinates| Anthro
    Slider <-->|Byte-identical PNG| Storage

    Router --> Auth
    Router --> Anthro
    Router --> Sizing
    Router --> JobQueue

    Auth <--> Mongo
    Anthro <--> Mongo
    Sizing <--> Mongo
    JobQueue <--> PG
    Router <--> Storage

    ColabBridge <-->|Auto Heartbeat & Tunnel Sync| Tunnel
    JobQueue -->|Lossless WebP/PNG Job Dispatch| Tunnel
    Tunnel <--> Worker
    Worker --> VTON
```

---

## 💻 Tech Stack

| Domain | Technology | Details |
|---|---|---|
| **Frontend UI** | React 19.1.0, TypeScript 5.8, Vite 6.4 | Modern SPA, Strict Type Safety, Fast HMR |
| **State & Forms** | React Hook Form 7.65, Zod 4.1, Lucide React | Declarative validation and editorial iconography |
| **Backend API** | Python 3.12, FastAPI 0.162, Starlette, Uvicorn | Async HTTP server, OpenAPI 3.1, Pydantic v2 validation |
| **Authentication** | Argon2id, PyJWT, SameSite Strict Cookies | Rotating HttpOnly session cookies, in-memory short-lived JWTs |
| **Computer Vision** | Google MediaPipe 0.10.21, OpenCV 4.11 | CPU Pose Landmarker Full, GrabCut segmentation |
| **Virtual Try-On** | PyTorch, FASHN VTON 1.5, Diffusers | Remote GPU FP16 generation, guidance 1.5, 576x864 resolution |
| **Databases** | MongoDB Community 8.2 & PostgreSQL 17 | Atomic versioned sizing charts, user scans, job state |
| **Database ORM/ODM** | PyMongo 4.19, SQLAlchemy 2.0, Alembic 1.16 | Auto schema migrations, relational run logs |
| **Testing & QA** | Pytest 9.1, Playwright 1.64, Ruff 0.11 | Integration tests, E2E browser tests, Python linting |

---

## 📁 Project Directory Structure

```text
Avatar_Virtual_try_on/
├── backend/
│   ├── app/
│   │   ├── accounts/             # User auth, Argon2id hashing, session lifecycle, JWT
│   │   ├── anthropometry/        # MediaPipe pose extraction, GrabCut silhouette & measurements
│   │   ├── catalog.py            # Reference garment catalog API
│   │   ├── charts.py             # Sizing charts & seed fixtures
│   │   ├── colab_connection.py   # Automatic Colab background health monitor
│   │   ├── config.py             # Pydantic environment configuration
│   │   ├── db.py                 # SQLAlchemy connection & session factory
│   │   ├── garments.py           # Garment upload & validation routes
│   │   ├── health.py             # Independent capability readiness probes
│   │   ├── jobs.py               # Try-on job queue, status tracking & idempotency
│   │   ├── main.py               # FastAPI entry point & router mounting
│   │   ├── online_vton.py        # Remote Colab client & image processing
│   │   ├── pipeline.py           # Try-on orchestrator & fallback protection
│   │   ├── private_data.py       # User-owned assets & scan security
│   │   └── schemas.py            # Pydantic request/response models
│   └── migrations/               # Alembic database migration scripts
├── frontend/
│   ├── src/
│   │   ├── components/           # UI components (Comparison Slider, Landmark Canvas, Header)
│   │   ├── context/              # AuthContext, MeasurementContext
│   │   ├── pages/                # Measure, Sizing, TryOn, Closet, Profile, Auth pages
│   │   ├── services/             # Axios/Fetch API client bindings
│   │   └── types/                # TypeScript interfaces & API contracts
│   ├── package.json              # Frontend npm dependencies
│   └── vite.config.ts            # Vite bundler configuration
├── ml/
│   ├── anthropometry/            # Anthropometric calculation formulas & pose calibration
│   ├── sizing/                   # Exact midpoint & interval sizing algorithms
│   └── vton/                     # Category mappings, mask generation & visual validators
├── scripts/
│   ├── setup.ps1                 # Master Windows installation script
│   ├── start.ps1                 # Master Windows runtime launcher
│   ├── stop.ps1                  # Graceful shutdown of servers & databases
│   ├── setup_colab_bridge.py     # Colab connection setup & pairing assistant
│   ├── online_worker.py          # Google Colab GPU worker server
│   ├── download_measurement_model.py # Fetch official MediaPipe landmark checkpoint
│   ├── start_mongodb.py          # Embedded/Local MongoDB orchestrator
│   └── start-postgres.ps1        # Portable PostgreSQL runner
├── docs/                         # Comprehensive engineering specifications
│   ├── api.md                    # Complete OpenAPI REST endpoints specification
│   ├── automatic-colab.md        # Colab tunnel discovery & self-healing architecture
│   ├── frontend-studio.md        # React studio guides, UX state & accessibility
│   ├── measurements-and-sizing.md# Mathematical formulas & pose extraction specs
│   └── requirements.md           # System constraints & acceptance criteria
├── tests/                        # Full test suite (Pytest integration & unit tests)
├── docker-compose.yml            # Containerized PostgreSQL & MongoDB services
├── pyproject.toml                # Project metadata & Ruff linter rules
└── README.md                     # You are here
```

---

## ⚙️ Prerequisites

Before installing, ensure your environment meets the following specifications:

- **Operating System**: Windows 10/11 (64-bit)
- **Python**: `3.12.x` (Python 3.11 to 3.12 supported; Python 3.12 recommended)
- **Node.js**: `20.x` or later (with `npm`)
- **Git**: Installed and available in `PATH`
- **Databases**:
  - **PostgreSQL 16+** (automated portable installation provided via `scripts/setup.ps1` or run via Docker)
  - **MongoDB Community 8.x** (or run via Docker on port 27018)
- **Google Account**: Access to [Google Colab](https://colab.research.google.com/) (Standard free T4 GPU tier is sufficient).

---

## 🚀 Quick Start Guide (Windows)

### 1. Clone the Repository
```powershell
git clone https://github.com/your-username/Avatar_Virtual_try_on.git
cd Avatar_Virtual_try_on
```

### 2. Run Automated Setup
The setup script configures the Python virtual environment (`.venv`), installs all locked dependencies, downloads the MediaPipe pose model, initializes the local databases, and builds the frontend:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

*(Alternatively, if using Docker for databases: run `docker compose up -d` before starting)*.

### 3. Start the Application
Launch both backend (FastAPI) and frontend (Vite) services simultaneously:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

Once running, the services will be accessible at:
- 🌐 **Frontend Studio**: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- 📚 **Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 🩺 **Health Check**: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

To stop all running services cleanly:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop.ps1
```

---

## ⚡ Google Colab GPU Worker Setup

VastraView offloads heavy diffusion inference to your own private Google Colab notebook.

### How It Works
1. **Automated Tunneling**: The worker generates a private, encrypted reverse tunnel (via ngrok/localtunnel) and an authentication token.
2. **Zero Invalidation**: Your credentials and tunnel endpoint are saved locally in `.runtime/colab-bridge/connection.json` (git-ignored).
3. **Self-Healing Bridge**: The FastAPI backend continuously checks worker health in the background. If Colab disconnects or reconnects, the backend auto-adopts the new tunnel without requiring an app restart.

### Setting Up Your Worker
1. Open [Google Colab](https://colab.research.google.com/) and create a new notebook (or use the helper script: `python scripts/setup_colab_bridge.py`).
2. Set Runtime Type to **GPU** (`Runtime -> Change runtime type -> T4 GPU`).
3. Clone or copy the worker script into Colab:
   ```python
   !git clone https://github.com/your-username/Avatar_Virtual_try_on.git /content/app
   %cd /content/app
   !pip install -r requirements-colab.txt
   !python scripts/online_worker.py --port 8080
   ```
4. Copy the generated Tunnel URL and Token output from the Colab notebook.
5. Update your local `.env`:
   ```dotenv
   ONLINE_VTON_URL=https://your-tunnel-url.trycloudflare.com
   ONLINE_VTON_TOKEN=your_generated_worker_token
   ONLINE_AUTO_CONNECT=true
   ```
6. The VastraView backend will automatically detect the worker and report green readiness on the frontend try-on studio!

---

## 🔄 Core Workflows

### 1. 2D Photo Virtual Try-On
1. Navigate to `/tryon`.
2. **Upload Person Image**: Front-facing portrait or full-body photo with clean lighting (JPG/PNG/WebP, up to 12 MB).
3. **Select Garment**: Choose from 57 editorial catalog items or upload your own flat-lay/model garment.
4. **Select Category**: Choose the garment category (*e.g., T-shirt, Dress, Jeans*).
5. **Generate**: Click **Generate Try-On**. The job is submitted asynchronously to the Colab GPU.
6. **Compare & Download**: Inspect results using the interactive Before/After Split Slider, zoom in on fabric details, and download the lossless PNG.

### 2. CPU Body Measurement & Anthropometry
1. Navigate to `/measure`.
2. Upload a full-body standing photo (arms slightly away from torso, upright posture) or capture via webcam.
3. Input your exact height in cm or ft/in.
4. The local CPU MediaPipe model identifies all 33 landmarks and computes 6 key anatomical dimensions.
5. Review the annotated landmark canvas and adjust values manually if desired before saving to your profile.

### 3. Intelligent Brand Size Recommendation
1. Navigate to `/sizing`.
2. Select your brand (*Nike, Puma, Levi's, Adidas, H&M, etc.*) and garment type.
3. Pull your measurements automatically from your saved scan or enter them manually.
4. The system calculates exact midpoint deviations against the brand's official measurement ranges, outputting your recommended size (*e.g., Size M - 94% Fit Score*) along with detailed per-measurement fit indicators.

---

## 📡 API Reference

Interactive OpenAPI documentation is hosted at `http://127.0.0.1:8000/docs`.

### Authentication & Profiles (`/api/v1/auth`, `/api/v1/profile`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/signup` | Create account (Argon2id password, returns JWT & HttpOnly cookie) |
| `POST` | `/api/v1/auth/login` | Authenticate user session |
| `POST` | `/api/v1/auth/refresh` | Atomically rotate refresh token |
| `POST` | `/api/v1/auth/logout` | Revoke session and invalidate cookies |
| `GET` | `/api/v1/profile` | Retrieve authenticated user profile |
| `POST` | `/api/v1/profile/scans` | Save body scan measurements with authenticated thumbnail |
| `GET` | `/api/v1/profile/scans` | List historical user scans (paginated) |

### Anthropometry & Sizing (`/api/v1/measurements`, `/api/v1/sizing`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/measurements/extract` | Extract 6 body metrics from image and height (CPU MediaPipe) |
| `POST` | `/api/v1/measurements/extract-and-recommend` | Single-step scan extraction and brand size matching |
| `GET` | `/api/v1/measurements/{id}/annotation` | Retrieve annotated landmark PNG visualization |
| `POST` | `/api/v1/sizing/recommend` | Compute brand size recommendations using midpoint error scoring |
| `GET` | `/api/v1/sizing/brands` | List supported apparel brands and available chart scopes |
| `GET` | `/api/v1/sizing/charts/{brand_id}/{apparel_id}` | Retrieve versioned sizing chart |

### Virtual Try-On Jobs (`/api/tryon`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/tryon` | Submit person & garment image for Colab GPU synthesis |
| `GET` | `/api/tryon/jobs/{job_id}` | Poll asynchronous job status (`queued`, `processing`, `success`, `failed`) |
| `GET` | `/api/runs/{uuid}` | Fetch persisted try-on run metadata and comparison artifacts |

### System Health (`/api/v1/health`)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health/live` | Basic process liveness probe |
| `GET` | `/api/v1/health` | Comprehensive component status (DB, Worker, Models) |
| `GET` | `/api/v1/health/ready` | Readiness check by capability (`?capability=tryon` or `measurements`) |

---

## 🔧 Environment Configuration

Configuration is managed via `.env` in the root directory. Key options:

```dotenv
# Databases
DATABASE_URL=postgresql+psycopg://tryon:tryon_local_only@127.0.0.1:5433/tryon
MONGODB_URI=mongodb://127.0.0.1:27018
MONGODB_DATABASE=formfit_measurements

# Colab VTON GPU Worker
ONLINE_VTON_URL=
ONLINE_VTON_TOKEN=
ONLINE_VTON_STEPS=10
ONLINE_VTON_TIMEOUT=600
ONLINE_AUTO_CONNECT=true

# Security & Sessions
AUTH_SECRET=your_random_32_character_secret_key_here
AUTH_COOKIE_SECURE=false
CORS_ORIGINS=["http://127.0.0.1:5173","http://localhost:5173"]

# Anthropometry Settings
MEASUREMENT_MODEL_PATH=assets/pose/pose_landmarker_full.task
MEASUREMENT_OUTPUT_ROOT=data/processed/measurements
MAX_UPLOAD_MB=12
```

---

## 🧪 Testing & Quality Assurance

### Run Backend Unit & Integration Tests
```powershell
.venv/Scripts/python.exe -m pytest tests/ -v
```

### Run Python Linting & Formatting (Ruff)
```powershell
.venv/Scripts/python.exe -m ruff check .
```

### Run Frontend End-to-End Tests (Playwright)
```powershell
cd frontend
npm run test:e2e
```

### Type Checking & Frontend Build Verification
```powershell
cd frontend
npm run build
```

---

## 🔐 Security & Privacy

- **Data Privacy**: Person and garment photos submitted for virtual try-on are sent **only** to your private Google Colab notebook instance. No third-party AI image APIs receive user photos.
- **Robust Authentication**: Passwords hashed with **Argon2id**. JWTs remain strictly in browser memory (never stored in `localStorage` or `sessionStorage`), protecting against XSS token exfiltration.
- **CSRF & Refresh Protection**: Sensitive state transitions utilize HttpOnly, SameSite=Strict cookies with atomic single-use refresh token rotation and multi-tab Web Locks synchronization.
- **Automatic Asset Retention**: Configurable background cleanup scripts (`scripts/cleanup_private_data.py`) purge temporary generation caches and guest sessions.

---

## 📖 Detailed Documentation Index

For in-depth architectural guides, refer to the documents in `docs/`:
- [API Contract Specification](docs/api.md): Exhaustive parameters, error codes, and request bodies.
- [Automatic Colab Connection](docs/automatic-colab.md): Tunnel discovery, host handshake, and self-healing worker details.
- [Body Estimates & Brand Sizing](docs/measurements-and-sizing.md): Landmark geometry, GrabCut silhouette tuning, and sizing formulas.
- [Frontend Studio Design](docs/frontend-studio.md): React architecture, accessibility, and route lifecycle.
- [Current System Requirements](docs/requirements.md): Quality targets, accepted garment types, and known boundaries.
- [India Brand Sources](docs/india-brand-sources.md): Catalog of sourced brand charts and verification records.

---

## ❓ Troubleshooting & FAQ

### Q: Port 8000 or 5173 is already in use
**A:** Another instance of VastraView or a background process is holding the port. Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop.ps1
```
Or check running processes on Windows:
```powershell
Get-NetTCPConnection -LocalPort 8000,5173,27018,5433 | Select-Object OwningProcess, LocalPort
```

### Q: Colab worker shows "Disconnected" or "503 Service Unavailable"
**A:**
1. Check your Google Colab tab to make sure the session has not timed out or exceeded Colab's idle threshold.
2. If Colab assigned a new IP or generated a new tunnel, the backend auto-connect daemon will locate it within 15–30 seconds.
3. You can verify tunnel reachability via `http://127.0.0.1:8000/api/v1/health/ready?capability=tryon`.

### Q: Anthropometry extract fails with "landmark visibility too low"
**A:** MediaPipe requires clear visibility (>0.65) of all 33 body points. Ensure:
- The full body is in the frame (from top of head to heels).
- The subject is facing forward with arms slightly spaced from the torso.
- The lighting is uniform with sufficient contrast against the background.

---

## 📄 License & Attribution

This project is licensed under the MIT License.
- **FASHN VTON 1.5**: Checkpoint and model adapter weights are subject to their respective research/commercial licenses.
- **Google MediaPipe**: Licensed under the Apache 2.0 License.
- **Garment References**: Sourced from open e-commerce and curated catalog fixtures for research and evaluation purposes.
