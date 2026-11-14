FROM ubuntu:24.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-openpyxl libreoffice-calc curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /root
RUN mkdir -p /root/data /root/output

FROM runtime AS task
COPY test-rar.xlsx gold-prices.xlsx /root/data/
