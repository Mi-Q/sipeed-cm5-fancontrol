FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/Mi-Q/sipeed-cm5-fancontrol"
LABEL org.opencontainers.image.description="PWM fan controller for Sipeed CM5 modules"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install build dependencies for lgpio and RPi.GPIO
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        curl \
        ca-certificates \
        libgpiod-dev \
        swig \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies including kubernetes client, lgpio (for k8s), and RPi.GPIO (fallback)
RUN pip install --no-cache-dir kubernetes lgpio RPi.GPIO

COPY deploy-systemd/fan_control.py /app/
COPY deploy-kubernetes/k8s_discovery.py /app/

ENV PYTHONUNBUFFERED=1

CMD ["python3", "/app/fan_control.py"]
