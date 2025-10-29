FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/Mi-Q/sipeed-cm5-fancontrol"
LABEL org.opencontainers.image.description="PWM fan controller for Sipeed CM5 modules"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install Python dependencies including kubernetes client
RUN pip install --no-cache-dir kubernetes

# Minimal runtime deps; gpio libs can be provided by the host when running privileged
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY deploy-systemd/fan_control.py /app/
COPY deploy-kubernetes/k8s_discovery.py /app/

ENV PYTHONUNBUFFERED=1

CMD ["python3", "/app/fan_control.py"]
