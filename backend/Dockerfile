FROM python:3.12-slim

# Install system dependencies + Node.js (for SAP RFC bridge)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies for RFC bridge
COPY package.json .
RUN npm install --omit=dev

# Copy application code
COPY app/ app/
COPY sap_rfc_bridge.js .

# Create uploads directory
RUN mkdir -p uploads

# Run as non-root user for security
RUN useradd -r -u 1001 -g root docai && \
    chown -R docai:root /app
USER docai

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
