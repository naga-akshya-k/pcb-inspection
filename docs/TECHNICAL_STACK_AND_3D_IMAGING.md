# Industrial PCB AI Inspection & 3D Metrology Suite
## Comprehensive Technical Stack, Photometric 3D, and Imaging Architecture Specification

---

## 1. Executive Technical Summary

This document specifies the technical stack, mathematical models, optical physics, and complete image processing pipeline of the **Industrial PCB / Motherboard AI Inspection & Metrology Suite**. 

The system delivers hardware-free 3D metrology and defect detection for Surface Mount Technology (SMT) and Printed Circuit Board Assembly (PCBA) by fusing:
1. **Multi-Angle Photometric Stereo** with 2D Fast Fourier Transform (FFT) Poisson height integration.
2. **Deep Monocular Depth Estimation** (*Depth Anything V2*) with RANSAC 3D substrate-plane regression.
3. **Simulated 3D X-Ray Laminography** for subsurface solder voiding (BGA, QFN, THT).
4. **Sub-Pixel 2D Metrology** and Tri-Metric Defect Ensembles (CIE-LAB CLAHE, SSIM, NCC, Canny Edge).
5. **Industry 4.0 CFX-2591 Telemetry** and ISO 9001:2015 SHA-256 Audit Logging.

---

## 2. Complete Technical Stack Matrix

| Layer | Technology | Version | Purpose & Description |
| :--- | :--- | :--- | :--- |
| **Language Runtime** | **Python (CPython)** | `3.11.9 (64-bit)` | Core execution runtime hosting all numerical, AI, and ASGI server workloads. |
| **Web Server / ASGI** | **FastAPI** | `v0.141.1` | Asynchronous REST API framework routing inspection payloads, CAD files, and static assets. |
| **ASGI Web Server** | **Uvicorn** | `v0.52.4` | High-throughput asynchronous server supporting concurrency and threadpool offloading. |
| **Concurrency & Workers**| **Starlette / AnyIO** | `4.14.2` | Manages non-blocking threadpools (`run_in_threadpool`) for CPU/GPU-intensive image processing. |
| **HTTP Protocols** | **python-multipart** / **Requests** | `0.0.32` / `2.34.2` | Multipart binary image upload decoding and edge-to-server HTTP client. |
| **Computer Vision** | **OpenCV (`cv2`)** | `5.0.0.93` | ORB feature detection, RANSAC homography, bilateral filtering, CIE-LAB conversion, morphology, and colormapping. |
| **Image Analysis** | **scikit-image** | `0.26.0` | Structural Similarity Index (SSIM) measurement, normalized cross-correlation, and image filters. |
| **Image IO & Buffering** | **Pillow (PIL)** | `12.3.0` | Memory-efficient in-memory buffer transformations and base64 conversions. |
| **Deep Learning** | **PyTorch (`torch`)** | `2.5.1+cu121` | GPU/CPU tensor execution engine for deep foundation models. |
| **Vision Neural Nets** | **Torchvision** | `0.20.1+cu121` | Visual transformations and backbone normalization utilities. |
| **Transformer Models** | **Hugging Face Transformers** | `5.16.1` | Pipelines hosting *Depth Anything V2 Small* for dense monocular depth estimation. |
| **Array Computing** | **NumPy** | `2.4.6` | Vectorized multidimensional array manipulation, gradient fields, and coordinate transforms. |
| **Numerical Solvers** | **SciPy** | `1.17.1` | 2D Fast Fourier Transforms (`scipy.fft`), Poisson solvers, and cross-sectional numerical differentiation. |
| **Statistical Regression**| **scikit-learn** | `1.9.0` | RANSAC 3D ground-plane regression, PCA, and Gage R&R statistical modeling. |
| **Tabular Data** | **Pandas** | `3.0.5` | Ground-truth catalog parsing, Gage R&R ANOVA computation, and metrics aggregation. |
| **Reporting & Export** | **openpyxl** / **matplotlib** | `3.1.0` / `3.11.1` | Excel MSA workbook generation and static analytical chart rendering. |
| **Frontend UI** | **Vanilla HTML5 / CSS3 / ES6+** | Native | Single-Page Application (SPA) dashboard styled with an industrial dark theme. |
| **Interactive Analytics**| **Chart.js** | `v4.4` | Real-time SPC control charts (p-chart, c-chart), DPMO trends, and Gage R&R bar charts. |
| **3D Rendering** | **Three.js / WebGL** | `r128` | Real-time browser-based 3D mesh rendering for solder joints and board topographies. |
| **Automated Testing** | **pytest** | `9.1.1` | Comprehensive 43-test verification suite covering CV, depth, X-ray, and API routes. |

---

## 3. Photometric 3D Stereo & Solder Profiling Engine

Implemented in:
- [`server/pipeline/photometric_stereo.py`](file:///c:/Users/kthir/Downloads/pcb-image-processing-main/pcb-image-processing-main/server/pipeline/photometric_stereo.py)
- [`server/pipeline/solder_profiler.py`](file:///c:/Users/kthir/Downloads/pcb-image-processing-main/pcb-image-processing-main/server/pipeline/solder_profiler.py)

### 3.1 Optical & Physical Illumination Model
The engine employs **Color-Coded Multi-Angle Photometric Stereo**. A single RGB capture acts as three simultaneous directional illumination sources:
- **Red Channel ($L_1$)**: High-angle direct illumination ($\theta = 75^\circ, \phi = 90^\circ$).
- **Green Channel ($L_2$)**: Mid-angle slope illumination ($\theta = 45^\circ, \phi = 210^\circ$).
- **Blue Channel ($L_3$)**: Grazing-angle slope illumination ($\theta = 20^\circ, \phi = 330^\circ$).

Light Direction Matrix $\mathbf{L}$:
$$\mathbf{L} = \begin{bmatrix} 0.0 & \sin(75^\circ) & \cos(75^\circ) \\ -\sin(45^\circ)\cos(30^\circ) & -\sin(45^\circ)\sin(30^\circ) & \cos(45^\circ) \\ \sin(20^\circ)\cos(30^\circ) & -\sin(20^\circ)\sin(30^\circ) & \cos(20^\circ) \end{bmatrix}$$

### 3.2 Inversion & Normal Recovery
From Lambertian reflectance $\mathbf{I} = \mathbf{L} \cdot \mathbf{G}$, the surface vector field $\mathbf{G} = \rho \mathbf{N}$ is solved using the Moore-Penrose pseudoinverse $\mathbf{L}^\dagger$:
$$\mathbf{G} = \mathbf{L}^\dagger \cdot \mathbf{I}$$
- **Albedo (Reflectance)**: $\rho(x, y) = \|\mathbf{G}(x, y)\|_2$
- **Unit Surface Normal**: $\mathbf{N}(x, y) = \frac{\mathbf{G}(x, y)}{\rho(x, y)} = \begin{bmatrix} N_x \\ N_y \\ N_z \end{bmatrix}$ (with $N_z$ clipped $\ge 0.05$).
- **Local Slope Angle**: $\alpha(x, y) = \arccos(\text{clip}(N_z, 0.0, 1.0)) \times \frac{180^\circ}{\pi}$.

### 3.3 2D FFT Poisson Elevation Integration
Converts surface gradients $p = -N_x / N_z$ and $q = -N_y / N_z$ into 3D topography via Poisson's equation $\nabla^2 Z = \frac{\partial p}{\partial x} + \frac{\partial q}{\partial y}$:
$$\mathcal{F}\{Z\}(u, v) = \frac{-i 2\pi u \mathcal{F}\{p\} - i 2\pi v \mathcal{F}\{q\}}{(2\pi u)^2 + (2\pi v)^2}$$
- Inverse FFT (`numpy.fft.ifft2`) produces continuous spatial elevation $Z(x, y)$.
- Scaled to physical units ($0\text{ to }180\,\mu\text{m}$) at a resolution of $2.5\,\mu\text{m/pixel}$.

### 3.4 IPC-A-610 Wetting Angle & Solder Classification
- **$< 12^\circ$**: *Insufficient Solder* (IPC Class 3 Violation: Non-wetting).
- **$15^\circ - 45^\circ$**: *Optimal Concave Meniscus* (IPC Class 3 Target: Good wetting fillet).
- **$45^\circ - 65^\circ$**: *Acceptable Class 2* (Slight excess solder).
- **$65^\circ - 75^\circ$**: *Excess Solder Bridge* (IPC Class 3 Violation: Convex bulge).
- **$> 75^\circ$**: *Tombstone / Lifted Lead* (IPC Class 3 Defect: Vertical termination).

### 3.5 Metrology & 3D Wavefront OBJ Mesh
- **Solder Paste Volume**: $V = \sum_{x, y \in \text{Pad}} Z(x, y) \cdot (\Delta x \cdot \Delta y)$ in nanoliters ($\text{nL}$).
- **IC Lead Coplanarity**: $\Delta Z = \max(Z) - \min(Z)$ across leads ($\le 50\,\mu\text{m}$ Class 3 limit).
- **Mesh Export**: Formats height maps into standard 3D Wavefront `.obj` files containing geometric vertices (`v x y z`) and triangulated face grids (`f v1 v2 v3`).

---

## 4. Monocular 3D Depth AI & Substrate Leveling

Implemented in:
- [`server/pipeline/detector_depth.py`](file:///c:/Users/kthir/Downloads/pcb-image-processing-main/pcb-image-processing-main/server/pipeline/detector_depth.py)
- [`server/pipeline/substrate_leveler.py`](file:///c:/Users/kthir/Downloads/pcb-image-processing-main/pcb-image-processing-main/server/pipeline/substrate_leveler.py)

### 4.1 Neural Depth Estimation
- **Model**: `depth-anything/Depth-Anything-V2-Small-hf`
- **Framework**: Hugging Face `transformers.pipeline("depth-estimation")`
- **Operation**: Infers relative metric depth maps directly from standard 2D RGB camera frames.

### 4.2 Algorithmic Fallback Engine
When GPU/transformer models are disabled, a deterministic edge-gradient depth model executes:
$$D(x, y) = 0.6 \cdot (255 - I_{\text{gray}}) + 0.4 \cdot \sqrt{\left(\frac{\partial I}{\partial x}\right)^2 + \left(\frac{\partial I}{\partial y}\right)^2}$$

### 4.3 RANSAC 3D Substrate Ground-Plane Regression
1. Samples bare substrate coordinates outside component ROIs on a 16-pixel grid.
2. Fits the 3D plane: $z = ax + by + c$ using RANSAC to reject outliers.
3. Subtracts the plane from raw depth values:
   $$\Delta Z_{\text{true}} = Z_{\text{raw}}(x, y) - (ax + by + c)$$
   This decouples camera slant and PCB warpage, revealing **true vertical component lift**.

---

## 5. Simulated 3D X-Ray (AXI) & Volumetric Laminography

Implemented in:
- [`server/pipeline/xray_engine.py`](file:///c:/Users/kthir/Downloads/pcb-image-processing-main/pcb-image-processing-main/server/pipeline/xray_engine.py)

### 5.1 Beer-Lambert Attenuation Physics
Simulates radiographic transmission through dense electronic components:
$$I(x, y) = I_0 \cdot \exp\left(-\sum_{s=0}^{N-1} \mu(x, y, s) \cdot \Delta z\right)$$

### 5.2 16-Slice Laminography Stack
Discretizes a $1,600\,\mu\text{m}$ thick PCB into 16 slices:
- **Slices 0–2**: Top surface metallization, IC packages, and solder paste.
- **Slices 3–5**: Hidden solder balls (BGA) and thermal ground pads (QFN).
- **Slices 6–10**: Inner power/ground planes and copper signal traces.
- **Slices 11–15**: Bottom copper traces and Plated Through-Hole (PTH) barrel pins.

### 5.3 Internal Solder Joint Diagnostics
- **BGA Solder Ball Voiding**: $8 \times 8$ BGA matrix at $20\,\mu\text{m/px}$. Measures individual void area ratios against the **IPC-A-610 25% maximum void limit**.
- **QFN Thermal Pad Outgassing**: Computes total thermal pad void coverage.
- **THT Barrel Fill**: Calculates vertical solder penetration across barrel depth ($\ge 75\%$ required for Class 3).

---

## 6. 2D Computer Vision & Optical Registration Pipeline

Implemented in:
- [`server/pipeline/aligner.py`](file:///c:/Users/kthir/Downloads/pcb-image-processing-main/pcb-image-processing-main/server/pipeline/aligner.py)
- [`server/pipeline/detector_2d.py`](file:///c:/Users/kthir/Downloads/pcb-image-processing-main/pcb-image-processing-main/server/pipeline/detector_2d.py)

### 6.1 Geometric Homography Registration
- **Optical Gating**: Computes Laplacian variance $\sigma^2(\nabla^2 I)$; rejects images below $50.0$ blur threshold.
- **Bilateral Filtering**: `cv2.bilateralFilter(d=9, sigmaColor=75, sigmaSpace=75)` removes noise while preserving trace edges.
- **ORB Feature Matching**: Detects 2,000 ORB keypoints, matched with Hamming distance.
- **RANSAC Homography**: Solves $3 \times 3$ transformation matrix $H$ with $3.0\,\text{px}$ reprojection threshold to align test images to the golden reference board.

### 6.2 CIE-LAB Specular Glare Suppression
- Converts RGB to CIE-LAB color space.
- Soft-clips specular reflections on solder surfaces ($L > 240 \rightarrow 230$).
- Applies CLAHE (`clipLimit=2.5, tileGridSize=(8, 8)`) to equalize illumination variations.

### 6.3 Tri-Metric Defect Detection Ensemble
$$\text{Ensemble Score} = 0.50 \cdot \text{SSIM} + 0.30 \cdot \text{NCC} + 0.20 \cdot (1.0 - \text{EdgeDiffRatio})$$
- **SSIM**: Structural similarity across $8 \times 8$ windows.
- **NCC**: Normalized Cross-Correlation (`cv2.TM_CCORR_NORMED`).
- **Edge Difference**: Canny gradient divergence between test and reference ROIs.

---

## 7. Complete Catalog of Datasets & Image Assets

### 7.1 Golden Calibration References (`server/reference/`)
| File | Dimensions | Type | Description |
| :--- | :--- | :--- | :--- |
| `golden_board.png` | $1024 \times 1024$ | 24-bit PNG | Calibrated perfect PCB image used as the 2D baseline answer key. |
| `golden_depth.npy` | $1024 \times 1024$ | Float32 NumPy | Precomputed reference baseline depth matrix. |

### 7.2 Photometric Solder Meniscus Samples (`server/static/photometric_samples/`)
| Sample File | Resolution | IPC-A-610 Condition | Wetting Angle | Height ($\mu\text{m}$) |
| :--- | :--- | :--- | :--- | :--- |
| `ps_sample_optimal.png` | $256 \times 256$ | IPC Class 3 Target Concave Meniscus | $28.4^\circ$ | $138.2\,\mu\text{m}$ |
| `ps_sample_excess.png` | $256 \times 256$ | Excess Solder / Bridge Bulge | $68.1^\circ$ | $174.5\,\mu\text{m}$ |
| `ps_sample_insufficient.png` | $256 \times 256$ | Starved / Insufficient Wetting | $9.3^\circ$ | $32.0\,\mu\text{m}$ |
| `ps_sample_tombstone.png` | $256 \times 256$ | Tombstoning / Vertical Lift | $79.6^\circ$ | $180.0\,\mu\text{m}$ |
| `ps_sample_burn.png` | $512 \times 512$ | Severe Thermal Rupture & Charring | N/A | Defect |

### 7.3 Evaluation & MSA Benchmark Dataset (`evaluation/test_boards/`)
33 physical test boards calibrated for Gage R&R and benchmarking:
- **`TB001.png` – `TB009.png`**: Perfect golden reference boards under variable optical lighting.
- **`TB010.png` – `TB022.png`**: Missing component defects across U1, U2, U3, U4, U5, C_R1, and connector pins.
- **`TB023.png` – `TB024.png`**: Tombstone defects (vertical height asymmetry $\ge 2.8\,\text{mm}$).
- **`TB025.png` – `TB026.png`**: Component angular skew/tilt defects ($18^\circ - 22^\circ$).
- **`TB027.png` – `TB028.png`**: Component placement shift defects ($1.5 - 1.8\,\text{mm}$ offset).
- **`TB029.png` – `TB030.png`**: Optical framing drift variations ($\pm 8\,\text{px}$).
- **`TB031.png`**: Multi-defect board (missing ICs + connector shifts).
- **`TB032.png`**: Catastrophic thermal burn defect.
- **`ai_hd_xray.png`**: High-resolution X-ray benchmark board.

---

## 8. Summary of Colormaps, Encodings & Resolutions

| Output Representation | Colormap / Encoding | Format | Native Resolution |
| :--- | :--- | :--- | :--- |
| **Photometric Surface Normals** | Vector encoding: $(N_x, N_y, N_z) \cdot 0.5 + 0.5$ | 8-bit RGB PNG / Base64 | $2.5\,\mu\text{m / pixel}$ |
| **Slope / Wetting Heatmap** | OpenCV `COLORMAP_INFERNO` ($0^\circ - 90^\circ$) | 8-bit BGR PNG / Base64 | $2.5\,\mu\text{m / pixel}$ |
| **3D Monocular Depth Map** | Grayscale / `COLORMAP_JET` ($0.0 - 1.0$) | Float32 NumPy / Base64 | $0.05\,\text{mm / pixel}$ |
| **Full X-Ray Radiograph** | OpenCV `COLORMAP_BONE` | 8-bit BGR PNG / Base64 | $20.0\,\mu\text{m / pixel}$ |
| **X-Ray Solder / Copper Layers** | OpenCV `COLORMAP_INFERNO` | 8-bit BGR PNG / Base64 | $20.0\,\mu\text{m / pixel}$ |
| **3D Topographic Mesh** | Wavefront `.obj` (Triangulated Quad Grid) | Plain text ASCII | $X, Y, Z \text{ in } \mu\text{m}$ |
| **Inspection Overlay HUD** | Color-coded markers & metrology callouts | 8-bit BGR PNG / Base64 | Native board px |
