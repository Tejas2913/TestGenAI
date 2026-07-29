# =============================================================================
# TestGen AI — Sandbox Execution Image
#
# Builds a minimal Python image with pytest pre-installed.
# The SandboxExecutor mounts generated test code into this container at
# runtime and invokes:  python -m pytest /test_code.py --tb=short -q
#
# Security constraints applied at runtime by executor.py (not here):
#   --network none        — no outbound connectivity
#   --memory / --cpus     — resource limits
#   --read-only           — immutable root filesystem
#   --tmpfs=/tmp          — writable scratch only
#   --security-opt no-new-privileges
#   --rm                  — auto-remove on exit
#
# Build:
#   docker build -t testgen-sandbox:latest ./sandbox
#
# Do NOT run this image directly — it is only used by the SandboxExecutor.
# =============================================================================

FROM python:3.11-slim

# ── Labels ────────────────────────────────────────────────────────────────────
LABEL maintainer="TestGen AI"
LABEL description="Isolated pytest execution environment"
LABEL version="1.0.0"

# ── System hardening ──────────────────────────────────────────────────────────
# Disable pip caching and bytecode to keep the image lean.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── Install pytest (pinned for reproducibility) ───────────────────────────────
# Only install what is needed to run pytest test files.
# No dev tools, no editors, no extra packages.
COPY requirements.txt /tmp/sandbox-requirements.txt
RUN pip install --no-cache-dir -r /tmp/sandbox-requirements.txt \
    && rm /tmp/sandbox-requirements.txt

# ── Non-root user ─────────────────────────────────────────────────────────────
# Running as root inside a container is a security risk even with --network none.
# The executor mounts test code as :ro, so the sandbox user only needs read access.
RUN groupadd --gid 10001 sandbox \
    && useradd --uid 10001 --gid sandbox --shell /sbin/nologin --no-create-home sandbox

USER sandbox

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /

# ── Default command ───────────────────────────────────────────────────────────
# The executor overrides this with the actual test file path.
# Defined here so the image is self-documenting.
CMD ["python", "-m", "pytest", "--help"]
