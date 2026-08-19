# ==============================================================================
# SpotDraft Assignment — Production Dockerfile
#
# Architecture (verified from full codebase):
#   - Entry point  : backend/main.py  →  app = FastAPI(lifespan=lifespan)
#   - Server       : uvicorn main:app  (WORKDIR /app/backend)
#   - Frontend     : /app/frontend  (served via Path(__file__).parent.parent/"frontend")
#   - GPU work     : Offloaded entirely to Modal.com — container is CPU-only
#   - Storage      : Supabase Storage (remote — no local volume needed)
#   - Vector DB    : Qdrant Cloud (remote)
#   - Relational DB: Supabase Postgres (remote, incl. LangGraph checkpointer via psycopg)
#   - LLM          : Mistral / Groq APIs (remote)
#
# Key build decisions:
#   1. Multi-stage build: builder installs deps, runner is a lean final image.
#   2. requirements.txt is UTF-16LE encoded (Windows artifact) — sanitized with iconv.
#   3. pywin32 is Windows-only; excluded from Linux build.
#   4. torch/torchvision versions in the freeze file don't exist on PyPI — we install
#      the latest stable CPU-only builds manually before pip processes requirements.
#   5. opencv-python (GUI build) conflicts with headless servers — replaced with headless.
#   6. HuggingFace tokenizer (BAAI/bge-base-en-v1.5) is imported at startup by
#      core/embedding_models.py — pre-downloaded in builder to avoid slow cold starts.
#   7. Non-root user "appuser" for security.
#   8. HEALTHCHECK included.
# ==============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — runtime-base
# Shared slim OS layer reused by both builder and final image.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=120 \
    # HuggingFace cache lives inside /app so the non-root user can write to it
    HF_HOME=/app/.cache/huggingface \
    # Suppress tokenizer parallelism warnings inside uvicorn workers
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

# Runtime-only OS libraries:
#   libpq5       — psycopg-binary needs this at runtime (LangGraph Postgres checkpointer)
#   libgomp1     — OpenMP runtime required by scikit-learn / numpy (used in chunk_service)
#   libglib2.0-0 — glib runtime pulled by opencv-python-headless transitively
#   curl         — used by the HEALTHCHECK probe
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libgomp1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — builder
# Compiles / installs all Python dependencies and pre-warms the HF cache.
# ─────────────────────────────────────────────────────────────────────────────
FROM runtime-base AS builder

# Build-time headers (not carried into the final image):
#   build-essential — compiles any C-extension wheels (e.g. lxml, cryptography)
#   libpq-dev       — needed to build psycopg from source if a wheel isn't available
#   iconv/iconv.h   — used below to re-encode requirements.txt (part of libc6-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Sanitize requirements.txt ─────────────────────────────────────────────────
# The file is UTF-16LE encoded (Windows pip freeze artifact — every character
# separated by a null byte and a leading BOM).  We re-encode it to UTF-8 and
# then strip Windows-specific / non-existent entries so pip can parse it cleanly.
#
# Removed entries:
#   pywin32          — Windows COM library, no Linux equivalent
#   torch==2.13.0    — version doesn't exist on PyPI (Windows local build artifact)
#   torchvision==0.28.0 — same reason
#   opencv-python==  — GUI build; crashes on headless Linux servers
#
# torch and torchvision are installed separately below with the CPU-only index.
# opencv-python-headless is already present in requirements.txt and is kept.
COPY backend/requirements.txt /tmp/requirements_raw.txt

RUN python3 - <<'PYEOF'
with open("/tmp/requirements_raw.txt", "rb") as f:
    raw = f.read()

# Strip UTF-16 BOM and decode
if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
    text = raw.decode("utf-16")
else:
    text = raw.decode("utf-8", errors="replace")

# Remove null bytes that survive utf-8 fallback
text = text.replace("\x00", "")

skip_prefixes = ("pywin32", "torch==", "torchvision==", "opencv-python==")
lines = []
for line in text.splitlines():
    stripped = line.strip()
    if any(stripped.lower().startswith(p.lower()) for p in skip_prefixes):
        continue
    lines.append(line)

with open("/tmp/requirements.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
PYEOF

# ── Install PyTorch (CPU-only) first ─────────────────────────────────────────
# Must precede the main requirements install so pip's dependency resolver doesn't
# pull the full 2 GB CUDA wheel from the default index.
# torch 2.6.0 + torchvision 0.21.0 is a valid stable pair compatible with
# transformers 5.x (used by core/embedding_models.py and services/chunk_service.py).
RUN pip install --no-cache-dir \
        torch==2.6.0 \
        torchvision==0.21.0 \
        --index-url https://download.pytorch.org/whl/cpu

# ── Install remaining requirements ───────────────────────────────────────────
# --no-deps for torch/torchvision is already handled above; pip will skip
# re-downloading them since they are already satisfied.
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ── Pre-download HuggingFace tokenizer ───────────────────────────────────────
# core/embedding_models.py calls AutoTokenizer.from_pretrained("BAAI/bge-base-en-v1.5")
# at *module import time* (i.e., on every cold start).  Baking the model files into
# the image eliminates the ~500 MB download on first container start.
RUN mkdir -p "${HF_HOME}" && python3 - <<'PYEOF'
from transformers import AutoTokenizer
# This call downloads the tokenizer config + vocab to $HF_HOME.
# The files are ~500 KB — very fast to download at build time.
AutoTokenizer.from_pretrained("BAAI/bge-base-en-v1.5")
print("Tokenizer pre-download complete.")
PYEOF


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — runner (final lean production image)
# ─────────────────────────────────────────────────────────────────────────────
FROM runtime-base AS runner

# Non-root user for security — follows least-privilege principle
RUN groupadd --system appuser && useradd --system --gid appuser --home /app --shell /sbin/nologin appuser

# Copy installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-warmed HuggingFace tokenizer cache
COPY --from=builder /app/.cache /app/.cache

# Copy application source
# backend/ must be at /app/backend  (main.py runs from here)
# frontend/ must be at /app/frontend (main.py references: Path(__file__).parent.parent / "frontend")
COPY backend  /app/backend
COPY frontend /app/frontend

# Fix ownership so the non-root user can write to the cache dir at runtime
RUN chown -R appuser:appuser /app

USER appuser
WORKDIR /app/backend

EXPOSE 8000

# ── Healthcheck ───────────────────────────────────────────────────────────────
# FastAPI's root path returns the login page HTML (HTTP 200).
# Adjust --start-period if startup migrations take longer in your environment.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# ── Start server ──────────────────────────────────────────────────────────────
# --workers 1: single worker is correct here because:
#   a) LangGraph's async Postgres checkpointer uses a module-level connection pool
#      (core/checkpointer.py) that is not safe to fork across multiple workers.
#   b) All I/O-bound work (LLM calls, Supabase, Qdrant) is already async.
# Scale horizontally by running multiple container replicas instead.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
