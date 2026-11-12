FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-calc-nogui python3-openpyxl \
    && rm -rf /var/lib/apt/lists/*
