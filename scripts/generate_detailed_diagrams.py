import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

os.makedirs("docs", exist_ok=True)

# ---------------------------------------------------------------------------
# 1. GENERATE DETAILED ARCHITECTURE DIAGRAM (Figure 1)
# ---------------------------------------------------------------------------
def create_detailed_system_architecture():
    fig, ax = plt.subplots(figsize=(16, 11), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')
    fig.patch.set_facecolor("#F8FAFC")

    # Header Title
    ax.text(50, 97.2, "VASTRAVIEW: DETAILED SYSTEM ARCHITECTURE", 
            fontsize=20, fontweight='bold', ha='center', va='center', color="#0F172A", family='sans-serif')
    ax.text(50, 94.6, "Full-Stack Multilayer Topology: Edge CPU Anthropometry & Remote Cloud GPU Diffusion VTON", 
            fontsize=11, fontstyle='italic', ha='center', va='center', color="#475569", family='sans-serif')

    # Color definitions
    c_client = "#E0F2FE"       # Light Sky
    c_client_border = "#0284C7"
    c_backend = "#DCFCE7"      # Light Emerald
    c_backend_border = "#16A34A"
    c_data = "#FEF3C7"         # Light Amber
    c_data_border = "#D97706"
    c_cloud = "#F3E8FF"        # Light Purple
    c_cloud_border = "#9333EA"
    c_box = "#FFFFFF"

    # ==========================
    # LAYER 1: CLIENT FRONTEND
    # ==========================
    l1 = patches.FancyBboxPatch((3, 74.5), 94, 18, boxstyle="round,pad=1.2,rounding_size=1.5",
                                facecolor=c_client, edgecolor=c_client_border, linewidth=2)
    ax.add_patch(l1)
    ax.text(5, 90.5, "1. CLIENT PRESENTATION TIER (React 19.1 + TypeScript 5.8 + Vite 6.4 — Port 5173)", 
            fontsize=11, fontweight='bold', color=c_client_border)

    c_boxes = [
        ("Acquisition & Ingestion", 
         "• HTML5 Webcam Live Stream Capture\n• Drag-and-Drop Image Uploader\n• EXIF Orientation & Mime Audit\n• Client Bounds: 256px - 12MB limit", 
         5, 76, 21.5, 12.5),
        ("Skeletal & Silhouette Canvas", 
         "• 33 3D Landmark Vector Visualization\n• Interactive Joint Adjustment Overlay\n• Real-Time GrabCut Contour Lines\n• Camera Silhouette Guides", 
         28.5, 76, 22, 12.5),
        ("Brand Sizing Workspace", 
         "• Dynamic Multi-Brand Selector\n• Fit Preference (Tight/Regular/Loose)\n• Fit Score (%) & Dimension Indicators\n• Dimension Breakdown (Chest, Waist)", 
         52.5, 76, 22, 12.5),
        ("Comparison Try-On Studio", 
         "• Interactive Split Slider (Before/After)\n• Dual Pan & Zoom Coordinate Sync\n• Curated 57-Garment Studio Wardrobe\n• Lossless PNG / WebP Export", 
         76.5, 76, 18.5, 12.5)
    ]
    for title, desc, x, y, w, h in c_boxes:
        b = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=0.8", facecolor=c_box, edgecolor=c_client_border, linewidth=1.2)
        ax.add_patch(b)
        ax.text(x + w/2, y + h - 2.2, title, fontsize=9, fontweight='bold', ha='center', va='center', color="#0F172A")
        ax.text(x + 1.0, y + (h/2) - 1.2, desc, fontsize=7.0, ha='left', va='center', color="#334155", linespacing=1.2)

    # ==========================
    # LAYER 2: BACKEND ENGINE
    # ==========================
    l2 = patches.FancyBboxPatch((3, 39.5), 94, 30, boxstyle="round,pad=1.2,rounding_size=1.5",
                                facecolor=c_backend, edgecolor=c_backend_border, linewidth=2)
    ax.add_patch(l2)
    ax.text(5, 67.5, "2. CORE APPLICATION & INTELLIGENCE TIER (Python 3.12 + FastAPI 0.162 + Uvicorn — Port 8000)", 
            fontsize=11, fontweight='bold', color=c_backend_border)

    b_boxes = [
        ("API Gateway & Security", 
         "• Argon2id Password Hashing\n• SameSite HttpOnly Auth Cookies\n• In-Memory Short-Lived JWT\n• Strict Pydantic v2 Request Filters\n• Health Probes (/api/v1/health)", 
         5, 41.5, 21.5, 24),
        ("Anthropometry Engine (CPU)", 
         "• MediaPipe Pose Landmarker Full\n• 33 Keypoints (x,y,z) with v > 0.65\n• Stature Ground Scale: s = H_true/H_px\n• Ramanujan Elliptical Slice Model:\n  Circumf = π[3(a+b) - √((3a+b)(a+3b))]\n• Slices: Shoulder, Chest, Waist, Hip", 
         28.5, 41.5, 23.5, 24),
        ("Deterministic Sizing Engine", 
         "• Midpoint Relative Euclidean Metric:\n  Error_s = Σ w_m * |d_m - midpoint| / tol\n• Weight Vector W:\n  Tops: Chest 0.50, Shld 0.35, Wst 0.15\n  Bottoms: Waist 0.50, Hip 0.35, Inseam 0.15\n• Fit Indicators (Ideal, Snug, Loose)", 
         54, 41.5, 22.5, 24),
        ("VTON Orchestrator", 
         "• Asynchronous Queue (.runtime/)\n• Lossless WebP Payload Packing\n• Category Garment Parse Masking\n• Lossless Identity Compositor:\n  Re-pastes Face, Skin & Background\n• Self-Healing Tunnel Monitor", 
         78.5, 41.5, 16.5, 24)
    ]
    for title, desc, x, y, w, h in b_boxes:
        b = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=0.8", facecolor=c_box, edgecolor=c_backend_border, linewidth=1.2)
        ax.add_patch(b)
        ax.text(x + w/2, y + h - 2.2, title, fontsize=9, fontweight='bold', ha='center', va='center', color="#0F172A")
        ax.text(x + 1.0, y + (h/2) - 1.2, desc, fontsize=7.0, ha='left', va='center', color="#334155")

    # ==========================
    # LAYER 3: STORAGE TIER
    # ==========================
    l3 = patches.FancyBboxPatch((3, 7), 45, 27.5, boxstyle="round,pad=1.2,rounding_size=1.5",
                                facecolor=c_data, edgecolor=c_data_border, linewidth=2)
    ax.add_patch(l3)
    ax.text(5, 32.5, "3. LOCAL PERSISTENCE & ASSET TIER", fontsize=10.5, fontweight='bold', color=c_data_border)

    d_boxes = [
        ("MongoDB Community 8.2\n(Port 27018 / PyMongo)", 
         "• 23 Sourced Brand Size Charts\n  (sourced-body-charts-v2.json)\n• Atomic (brand, category) indexes\n• User Biometric Scan Profiles\n• Private User Wardrobe Collections", 
         5, 9, 21, 21),
        ("PostgreSQL 17 & Filesystem\n(Port 5433 / SQLAlchemy)", 
         "• Asynchronous Try-On Job States\n• Pipeline Execution Audit Logs\n• File Store: /data/processed/\n• Curated 57 Reference Garments\n• Model Weights: pose_landmarker.task", 
         28, 9, 18, 21)
    ]
    for title, desc, x, y, w, h in d_boxes:
        b = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=0.8", facecolor=c_box, edgecolor=c_data_border, linewidth=1.2)
        ax.add_patch(b)
        ax.text(x + w/2, y + h - 2.5, title, fontsize=8.2, fontweight='bold', ha='center', va='center', color="#0F172A")
        ax.text(x + 1.0, y + (h/2) - 1.8, desc, fontsize=6.8, ha='left', va='center', color="#334155")

    # ==========================
    # LAYER 4: REMOTE CLUSTER
    # ==========================
    l4 = patches.FancyBboxPatch((52, 7), 45, 27.5, boxstyle="round,pad=1.2,rounding_size=1.5",
                                facecolor=c_cloud, edgecolor=c_cloud_border, linewidth=2)
    ax.add_patch(l4)
    ax.text(54, 32.5, "4. REMOTE GPU CLUSTER (Google Colab T4 / A100)", fontsize=10.5, fontweight='bold', color=c_cloud_border)

    cloud_boxes = [
        ("Reverse Tunnel Gateway\n(Cloudflare / ngrok)", 
         "• Zero Cloud Storage Requirement\n• Self-Healing Reconnect Bridge\n• Bearer Token Authentication\n• 3-Second Heartbeat Latency Poll", 
         54, 9, 19, 21),
        ("FASHN VTON 1.5 Worker\n(PyTorch / FP16 CUDA)", 
         "• online_worker.py (Port 8080)\n• 576x864 Latent Diffusion Inpainting\n• Deep Garment Deformation Network\n• 8.4s Inference per Generation\n• Lossless WebP Output Encoding", 
         75, 9, 20, 21)
    ]
    for title, desc, x, y, w, h in cloud_boxes:
        b = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=0.8", facecolor=c_box, edgecolor=c_cloud_border, linewidth=1.2)
        ax.add_patch(b)
        ax.text(x + w/2, y + h - 2.5, title, fontsize=8.2, fontweight='bold', ha='center', va='center', color="#0F172A")
        ax.text(x + 1.0, y + (h/2) - 1.8, desc, fontsize=6.8, ha='left', va='center', color="#334155")

    # ==========================
    # INTER-LAYER ARROWS
    # ==========================
    # Frontend <-> Backend
    ax.annotate('', xy=(15, 69.5), xytext=(15, 74.5), arrowprops=dict(arrowstyle="<->", color=c_client_border, lw=2))
    ax.text(16, 72, "REST JSON / Multipart", fontsize=7.5, fontweight='bold', color=c_client_border)

    ax.annotate('', xy=(40, 69.5), xytext=(40, 74.5), arrowprops=dict(arrowstyle="<->", color=c_backend_border, lw=2))
    ax.text(41, 72, "33-Keypoints & Bounds", fontsize=7.5, fontweight='bold', color=c_backend_border)

    ax.annotate('', xy=(85, 74.5), xytext=(85, 69.5), arrowprops=dict(arrowstyle="<-", color="#0284C7", lw=2))
    ax.text(86, 72, "Lossless PNG Render", fontsize=7.5, fontweight='bold', color="#0284C7")

    # Backend <-> Storage
    ax.annotate('', xy=(20, 39.5), xytext=(20, 34.5), arrowprops=dict(arrowstyle="<->", color=c_data_border, lw=2))
    ax.text(21, 37, "PyMongo / Relational Queries", fontsize=7.5, fontweight='bold', color=c_data_border)

    # Backend <-> Colab Tunnel
    ax.annotate('', xy=(72, 34.5), xytext=(85, 39.5), arrowprops=dict(arrowstyle="<->", color=c_cloud_border, lw=2))
    ax.text(77, 37, "Encrypted Tunnel / Job Dispatch", fontsize=7.5, fontweight='bold', color=c_cloud_border)

    plt.tight_layout()
    out_png = "docs/DETAILED_SYSTEM_ARCHITECTURE.png"
    out_pdf = "docs/DETAILED_SYSTEM_ARCHITECTURE.pdf"
    plt.savefig(out_png, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.savefig(out_pdf, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    print("Detailed Architecture saved to:", out_png, "and", out_pdf)
    return out_png, out_pdf

# ---------------------------------------------------------------------------
# 2. GENERATE DETAILED PIPELINE BLOCK DIAGRAM (Figure 2)
# ---------------------------------------------------------------------------
def create_detailed_block_diagram():
    fig, ax = plt.subplots(figsize=(16, 8.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis('off')
    fig.patch.set_facecolor("#FFFFFF")

    # Title
    ax.text(50, 56.5, "VASTRAVIEW: DETAILED FUNCTIONAL BLOCK & DATA-FLOW DIAGRAM", 
            fontsize=17, fontweight='bold', ha='center', va='center', color="#0F172A")
    ax.text(50, 53.2, "Mathematical Formulations, Thresholds, and Execution Stages across Pipeline", 
            fontsize=10.5, fontstyle='italic', ha='center', va='center', color="#475569")

    blocks = [
        ("STAGE 1: INPUT INGESTION",
         "• JPEG / PNG Upload / Webcam\n• Validation: >=256px, <=12MB\n• EXIF Orientation Normalization\n• User True Height: H_true (cm)\n  (Domain: 80 <= H_true <= 250)",
         3, 20, 14, 28, "#EFF6FF", "#3B82F6"),
        ("STAGE 2: POSE EXTRACTION",
         "• MediaPipe Tasks Pose Full (CPU)\n• 33 3D Keypoints (x, y, z)\n• Joint Visibility Filter: v > 0.65\n• Key Anchors: Shoulders, Hips,\n  Knees, Ankles, Heels\n• Low-Confidence Rejection (422)",
         19, 20, 14.5, 28, "#F0FDF4", "#22C55E"),
        ("STAGE 3: ANTHROPOMETRY",
         "• Stature Scale: s = H_true / H_px\n• Shoulder Breadth = Euclidean * s\n• Ramanujan Elliptical Slice:\n  C = π[3(a+b) - √((3a+b)(a+3b))]\n• Slices: Chest, Waist, Hip, Inseam\n• GrabCut Silhouette Separation",
         35.5, 20, 14.5, 28, "#FEF9C3", "#CA8A04"),
        ("STAGE 4: BRAND SIZING",
         "• Query 23 Atomic Brand Charts\n• Midpoint Error Calculation:\n  Error_s = Σ w_m * |d_m - mid| / tol\n• Weight Matrix W:\n  Tops: Chest 0.50, Shld 0.35, Wst 0.15\n• Output: Size (S..XXL) + Fit %",
         52, 20, 14.5, 28, "#FAF5FF", "#9333EA"),
        ("STAGE 5: REMOTE CLOUD VTON",
         "• Asynchronous Queue (.runtime/)\n• Encrypted Reverse Tunnel Dispatch\n• FASHN VTON 1.5 (Colab T4 GPU)\n• Latent Diffusion Inpainting (FP16)\n• Garment Warping (576x864 px)\n• Inference Time: ~8.4 seconds",
         68.5, 20, 14.5, 28, "#FFF1F2", "#E11D48"),
        ("STAGE 6: LOSSLESS COMPOSITE",
         "• Semantic Human Parsing Mask\n• Face / Skin / Hair Preserved\n• Background Region Preserved\n• Lossless Alpha Compositing\n• Interactive Before/After Split\n• Lossless PNG / WebP Studio View",
         85, 20, 12.5, 28, "#ECFEFF", "#0891B2"),
    ]

    for title, desc, x, y, w, h, bg, border in blocks:
        p = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=1.0", facecolor=bg, edgecolor=border, linewidth=2)
        ax.add_patch(p)
        ax.text(x + w/2, y + h - 3.0, title, fontsize=7.8, fontweight='bold', ha='center', va='center', color="#0F172A")
        ax.text(x + 0.6, y + (h/2) - 1.5, desc, fontsize=6.8, ha='left', va='center', color="#334155")

    # Connectors between stages
    for i in range(len(blocks) - 1):
        x1 = blocks[i][2] + blocks[i][4]
        x2 = blocks[i+1][2]
        y_mid = 20 + 14
        ax.annotate('', xy=(x2, y_mid), xytext=(x1, y_mid),
                    arrowprops=dict(arrowstyle="-|>", color="#475569", lw=2.2, mutation_scale=16))

    # Bottom Architectural Context Boxes
    ctx = [
        ("Client Browser", 3, 9, 14, 7, "#3B82F6"),
        ("FastAPI Server (CPU)", 19, 9, 31, 7, "#22C55E"),
        ("MongoDB Community", 52, 9, 14.5, 7, "#9333EA"),
        ("Google Colab (GPU)", 68.5, 9, 14.5, 7, "#E11D48"),
        ("React UI Studio", 85, 9, 12.5, 7, "#0891B2")
    ]
    for label, x, y, w, h, col in ctx:
        p = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=0.6", facecolor="#F8FAFC", edgecolor=col, linewidth=1.5, linestyle="--")
        ax.add_patch(p)
        ax.text(x + w/2, y + h/2, label, fontsize=8.2, fontweight='bold', ha='center', va='center', color=col)

    plt.tight_layout()
    block_png = "docs/DETAILED_FUNCTIONAL_BLOCK_DIAGRAM.png"
    block_pdf = "docs/DETAILED_FUNCTIONAL_BLOCK_DIAGRAM.pdf"
    plt.savefig(block_png, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.savefig(block_pdf, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    print("Detailed Block Diagram saved to:", block_png, "and", block_pdf)
    return block_png, block_pdf

# ---------------------------------------------------------------------------
# 3. BUILD DEDICATED HIGH-RES LANDSCAPE PDF DELIVERABLE
# ---------------------------------------------------------------------------
class DetailedNumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8.5)
        self.setFillColor(colors.HexColor("#475569"))
        # Top banner
        self.drawString(40, 8.5 * 72 - 28, "VASTRAVIEW: SYSTEM ARCHITECTURE & BLOCK DIAGRAM SPECIFICATION")
        self.setFont("Helvetica", 8)
        self.drawRightString(11.0 * 72 - 40, 8.5 * 72 - 28, "ACADEMIC PROJECT REPORT DELIVERABLE")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.7)
        self.line(40, 8.5 * 72 - 34, 11.0 * 72 - 40, 8.5 * 72 - 34)
        
        # Bottom footer
        self.line(40, 36, 11.0 * 72 - 40, 36)
        self.drawString(40, 24, "CONFIDENTIAL — Computer Science & Engineering Major Project")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(11.0 * 72 - 40, 24, page_str)
        self.restoreState()

def build_dedicated_diagram_pdf(arch_png, block_png):
    pdf_out = "docs/VASTRAVIEW_DETAILED_SYSTEM_AND_BLOCK_DIAGRAMS.pdf"
    doc = SimpleDocTemplate(
        pdf_out,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=42,
        bottomMargin=42
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('LandTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=colors.HexColor("#0F172A"), alignment=1)
    caption_style = ParagraphStyle('Cap', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=12, textColor=colors.HexColor("#334155"), alignment=1)
    h2_style = ParagraphStyle('H2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10.5, leading=14, textColor=colors.HexColor("#0284C7"), spaceBefore=6, spaceAfter=4)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontName='Helvetica', fontSize=7.8, leading=11, textColor=colors.HexColor("#1E293B"))

    story = []

    # PAGE 1: SYSTEM ARCHITECTURE
    story.append(Paragraph("SECTION 1: DETAILED MULTI-TIER SYSTEM ARCHITECTURE", title_style))
    story.append(Spacer(1, 4))
    story.append(Image(arch_png, width=10.0*72, height=6.2*72))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Figure 1.1: Multi-Tier Architectural Topology.</b> Depicts the physical and logical boundaries separating client-side presentation (React 19), deterministic edge CPU anthropometry (FastAPI / MediaPipe), local databases (PostgreSQL 17 / MongoDB 8.2), and the remote Google Colab GPU diffusion worker.", caption_style))
    story.append(PageBreak())

    # PAGE 2: FUNCTIONAL BLOCK & DATA-FLOW DIAGRAM
    story.append(Paragraph("SECTION 2: FUNCTIONAL PIPELINE & DATA-FLOW BLOCK DIAGRAM", title_style))
    story.append(Spacer(1, 4))
    story.append(Image(block_png, width=10.0*72, height=5.3*72))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Figure 1.2: End-to-End Functional Data Flow.</b> Details the 6 operational pipeline stages: image validation, 33-point CPU pose tracking, height-calibrated Ramanujan circumference computation, weighted brand chart matching, remote cloud GPU diffusion inpainting (FASHN VTON 1.5), and lossless identity composite output.", caption_style))
    story.append(PageBreak())

    # PAGE 3: TECHNICAL SPECIFICATIONS & ARCHITECTURAL EQUATIONS
    story.append(Paragraph("SECTION 3: ARCHITECTURAL EQUATIONS, DATAFLOWS & SUBSYSTEM CONTRACTS", title_style))
    story.append(Spacer(1, 8))

    spec_data = [
        ["Subsystem", "Implementation Details", "Mathematical Models & Thresholds", "Hardware Target"],
        ["1. Client Tier", "React 19.1, TypeScript 5.8, Vite 6.4\nHTML5 Canvas & WebRTC Camera Stream\nSplit-Screen Comparison Slider", "• Input resolution: 256px min, 12MB max\n• Viewport sync: dual pan/zoom coordinates\n• Export format: 24-bit sRGB PNG / WebP", "Client Browser\n(Desktop / Mobile)"],
        ["2. Anthropometry Engine", "FastAPI, MediaPipe Tasks Pose Full\nGrabCut Foreground Segmentation\nDeterministic coordinate transformation", "• Visibility acceptance threshold: v > 0.65\n• Stature scaling factor: s = H_true / |y_ground - y_crown|\n• Ramanujan Ellipse: C ≈ π[3(a+b) - √((3a+b)(a+3b))]", "Local Server CPU\n(No GPU required)"],
        ["3. Sizing Engine", "Atomic MongoDB Repository\n23 Sourced Brand Chart fixtures\n(Nike, Adidas, Puma, Levi's, H&M, Manyavar)", "• Weighted Error: Error_s = Σ w_m * |d_m - midpoint| / tol\n• Active Weights: Tops {Chest:0.50, Shld:0.35, Wst:0.15}\n• Bottoms {Waist:0.50, Hip:0.35, Inseam:0.15}", "Local Server CPU\n(MongoDB 27018)"],
        ["4. Remote Cloud GPU", "FASHN VTON 1.5 Diffusion Model\nPyTorch, CUDA 12.x, FP16 Inpainting\nSelf-healing reverse encrypted tunnel", "• Resolution: 576 x 864 pixels\n• Classifier-free guidance: 1.5, Latency: ~8.4s\n• Lossless composite: FaceMask & Background preserved", "Remote Google Colab\n(NVIDIA T4 / A100 GPU)"]
    ]
    t_spec = Table(spec_data, colWidths=[110, 210, 260, 140])
    t_spec.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_spec)

    doc.build(story, canvasmaker=DetailedNumberedCanvas)
    print("Dedicated Diagram PDF built at:", pdf_out)
    return pdf_out

if __name__ == "__main__":
    arch_png, arch_pdf = create_detailed_system_architecture()
    block_png, block_pdf = create_detailed_block_diagram()
    dedicated_pdf = build_dedicated_diagram_pdf(arch_png, block_png)
    print("ALL DETAILED DELIVERABLES GENERATED!")
