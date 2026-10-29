FROM python:3.11-slim-bookworm

WORKDIR /workspace/backend

# Install system dependencies for PDF export (wkhtmltopdf + CJK fonts)
# Default to official HTTPS repositories; allow a reachable signed mirror at build time.
ARG DEBIAN_MIRROR=https://deb.debian.org/debian
ARG DEBIAN_SECURITY_MIRROR=https://deb.debian.org/debian-security
RUN sed -i "s#http://deb.debian.org/debian-security#${DEBIAN_SECURITY_MIRROR}#g; s#http://deb.debian.org/debian#${DEBIAN_MIRROR}#g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends wkhtmltopdf fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Install only production dependencies
COPY requirements.txt .
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
RUN pip install --no-cache-dir -i "$PIP_INDEX_URL" -r requirements.txt

# Copy source code
COPY . .

# Create data directory for SQLite
RUN mkdir -p /workspace/backend/data /workspace/backend/exports

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
