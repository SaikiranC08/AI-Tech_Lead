FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for building native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (for layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Ensure Python output is sent straight to terminal (no buffering)
ENV PYTHONUNBUFFERED=1

# Render uses the PORT env var; default to 8000
EXPOSE 8000

CMD ["python", "-m", "src.ai_tech_lead_project.watcher_server"]
