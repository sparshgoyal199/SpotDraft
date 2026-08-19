import modal
from pathlib import Path

# ── Image ─────────────────────────────────────────────────────────────────────
# Build the same way as your Dockerfile: CPU-only torch first, then requirements.
# We read requirements.txt at image-build time.

def _sanitize_requirements():
    """Return cleaned requirements as a list of strings for pip_install."""
    req_path = Path(__file__).parent / "requirements.txt"
    raw = req_path.read_bytes()

    # Handle UTF-16 BOM (Windows pip freeze artifact)
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8", errors="replace")

    text = text.replace("\x00", "")

    # Skip Windows-only, non-existent PyPI versions, and packages
    # whose pinned versions were built on Python 3.14 and don't exist for 3.12.
    # numpy==2.5.2, pandas==3.0.5, scipy==1.18.0 etc. are 3.14-only builds —
    # let pip resolve the latest compatible version for 3.12 instead.
    # Also skip opencv-python (GUI) — we only want opencv-python-headless.
    skip = (
        "pywin32",
        "torch==",
        "torchvision==",
        "opencv-python==",
        "numpy==",
        "pandas==",
        "scipy==",
        "pyarrow==",
    )
    skip_exact = ("opencv-python",)  # exact match — GUI version, use headless instead
    
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if any(s.lower().startswith(p.lower()) for p in skip):
            continue
        # Check exact matches too
        pkg_name = s.split("==")[0].split(">=")[0].split("<=")[0].strip().lower()
        if pkg_name in [x.lower() for x in skip_exact]:
            continue
        lines.append(s)
    return lines

# Only run this locally, NOT inside the Modal container.
# Modal sets a special environment variable we can check.
import os
_is_in_modal = os.environ.get("MODAL_SERVER_URL") is not None

if _is_in_modal:
    # Inside container — requirements.txt doesn't exist here, but we don't need it
    # because the image was already built with the requirements installed.
    _REQUIREMENTS = []
else:
    # Local machine — read and sanitize requirements.txt
    _REQUIREMENTS = _sanitize_requirements()

# CPU-only torch must be installed before the rest of the requirements
# so Modal's pip resolver doesn't pull 2 GB CUDA wheels.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "libpq5",        # psycopg-binary runtime
        "libgomp1",      # scikit-learn / numpy OpenMP
        "libglib2.0-0",  # opencv-headless transitive dep
        "libgl1",        # OpenGL lib — sometimes needed by cv2 even in headless
        "curl",          # optional, healthchecks / debug
    )
    .pip_install(
        "torch==2.6.0",
        "torchvision==0.21.0",
        extra_index_url="https://download.pytorch.org/whl/cpu",
    )
    # Install numpy/pandas/scipy unpinned so pip picks versions compatible
    # with Python 3.12 (the pinned versions in requirements.txt were built
    # on Python 3.14 and don't exist for 3.12 on PyPI)
    .pip_install("numpy", "pandas", "scipy", "pyarrow")
    .pip_install(*_REQUIREMENTS)
    # Pre-cache the HuggingFace tokenizer used at import time by
    # core/embedding_models.py — avoids ~500 MB download on cold start.
    .run_commands(
        "python -c \""
        "from transformers import AutoTokenizer; "
        "AutoTokenizer.from_pretrained('BAAI/bge-base-en-v1.5')"
        "\""
    )
    # Add source files into the image (replaces modal.Mount — removed in Modal 1.0)
    # backend/ → /app/backend  (main.py entry point)
    # frontend/ → /app/frontend (main.py: Path(__file__).parent.parent / "frontend")
    # ignore= uses dockerignore-style rules to exclude junk/secrets
    .add_local_dir(
        ".",
        remote_path="/app/backend",
        ignore=[
            "venv",           # local virtualenv — never copy into image
            ".venv",
            ".env",           # secrets — injected via Modal Secret at runtime
            ".env.*",
            "__pycache__",
            "**/__pycache__",
            "*.pyc",
            "*.pyo",
            ".git",
            ".gitignore",
            "test_*.py",      # test scripts not needed at runtime
            "*.log",
            "*.db",
            "*.sqlite",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        ],
    )
    .add_local_dir("../frontend", remote_path="/app/frontend")
)

# ── App ───────────────────────────────────────────────────────────────────────
app = modal.App("spotdraft-fastapi-backend", image=image)

# All secrets injected via Modal Secrets (never baked into the image)
app_secrets = modal.Secret.from_name("spotdraft-secrets")

@app.function(
    secrets=[app_secrets],
    # CPU-only — GPU work is handled by the existing parsing_and_embedding_generator app
    cpu=2,
    memory=2048,
    # No min_containers — scale to zero when idle, spin up on request
    timeout=300,
)
@modal.asgi_app()
def fastapi_app():
    print("=== fastapi_app() called — container is alive ===")
    import sys
    sys.path.insert(0, "/app/backend")
    from main import app as _app
    print("=== FastAPI app imported successfully ===")
    return _app
