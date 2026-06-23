# =========================================================
# STAGE 1: Builder (Builds & downloads dependencies)
# =========================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install minimal system tools needed to compile packages if necessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into the user directory (/root/.local)
RUN pip install --no-cache-dir --user -r requirements.txt


# =========================================================
# STAGE 2: Runner (The clean, minimal production image)
# =========================================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Copy ONLY the installed python packages from the Builder stage
COPY --from=builder /root/.local /root/.local

# Ensure the python packages are in the system PATH
ENV PATH=/root/.local/bin:$PATH

# Copy our application source code (.dockerignore ignores the rest)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]