# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app


COPY zscaler-root.crt /usr/local/share/ca-certificates/zscaler-root.crt

# 2. FIX SSL: Update the container's CA store and set environment variables
# This allows 'pip' and 'requests' to trust your corporate proxy
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    update-ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Point pip to the updated certificate bundle
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV HF_HUB_CERTIFICATE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_DIR=/etc/ssl/certs

# Copy requirements and project files
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for Streamlit
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Refresh trust store at runtime so mounted corporate certs are always active.
CMD ["/bin/sh", "-c", "update-ca-certificates && streamlit run main.py --server.port=8501 --server.address=0.0.0.0"]
