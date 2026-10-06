# INSPECTRA Changelog

All notable changes to the INSPECTRA Intelligent PCB Inspection & Digital Twin Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0-baseline] - 2026-10-06
### Baseline Architecture
- **Core Vision Pipeline**:
  - `PCBAligner`: Laplacian variance blur gating, exposure distribution checks, ORB (5000 feats) + RANSAC homography, and sub-pixel ECC fallback.
  - `Detector2D`: CIE-LAB specular glare suppression, CLAHE, and Tri-Metric Ensemble ($0.50\,\text{SSIM} + 0.30\,\text{NCC} + 0.20\,\text{EdgeDiff}$).
  - `DetectorDepth` & `SubstrateLeveler`: Monocular depth estimation (Depth-Anything-V2 / Sobel fallback) with least-squares 3D substrate plane fitting to isolate component vertical lift.
  - `MetrologyEngine`: Sub-pixel $\Delta X, \Delta Y$ (mm), rotation $\Delta\theta$, overhang %, IPC-A-610 Class 2/3 thresholds, and Pin-1 polarity dot verification.
  - `CADParser`: SMT Pick-and-Place centroid CSV auto-ingestion.
  - `HealthIndexCalculator`: Continuous Health Index $HI \in [0, 1]$, DPMO calculation, and automated verdict mapping.
- **Physics & Subsurface Engines**:
  - `PhotometricStereoEngine`: Calibrated 3-angle RGB illumination matrix inversion for surface normal recovery and 2D FFT Poisson height integration.
  - `SolderProfilerEngine`: IPC-A-610 meniscus cross-sectional slicing, volume integration, IC lead coplanarity, and Wavefront `.obj` export.
  - `XRayEngine`: 16-slice radiographic volumetric attenuation simulation via Beer-Lambert Law with BGA voiding and THT barrel fill metrology.
- **Traceability & Factory Connectivity**:
  - `AuditLogger`: ISO 9001 SHA-256 cryptographic image hashing in an append-only JSONL format (`audit.jsonl`).
  - `CFXDispatcher`: IPC-CFX-2591 JSON telemetry with automated closed-loop feeder nozzle drift alerts.
- **Frontend & Visualization**:
  - 11 multi-page views: Live Inspection, 360° 3D Digital Twin, 3D Photometric Studio, 3D X-Ray Studio, Photometric Stereo, IPC Metrology, Analytics, SPC, MSA, CFX, and Audit.
  - 44 automated pytest tests passing with 100% success rate.

---

## [0.2.0-session] - 2026-10-06
### Added
- **Central `PCBInspectionSession` Architecture** (`server/pipeline/session_manager.py`):
  - Standardized unified session state model with unique auto-incrementing PCB ID format (`PCB-001248`).
  - Structured fields for Lot, Line, Station, Operator, Timestamp, Calibration version, Multimodal evidence, Defect items, AI explanation, and Human review adjudication.
  - `InspectionSessionManager` providing session registry, history buffer, and active session selection.
- **Real-Time Cross-Tab Event Bus** (`server/main.py` + `server/static/common.js`):
  - FastAPI `/api/events` Server-Sent Events (SSE) streaming endpoint with non-blocking `asyncio.Queue` subscribers.
  - Automated client-side bridge in `common.js` connecting `EventSource` to browser `BroadcastChannel('inspectra_global_bus')`.
  - Enables instant, simultaneous real-time synchronization across all open workstation browser tabs upon inspection completion or board selection.
- **Session REST API Endpoints**:
  - `GET /api/session/active`: Returns current active session.
  - `GET /api/session/{pcb_id}`: Retrieves specific session by ID or serial.
  - `GET /api/sessions/history`: Lists historical inspection sessions.
  - `POST /api/session/select/{pcb_id}`: Broadcasts active board switch to all tabs.
  - `POST /api/session/human-review`: Records operator review decision, comments, and AI verdict override.
- **Automated Test Suite**:
  - Added `tests/test_inspection_session.py` (3 new tests); total test suite expanded to 47 passing tests.
