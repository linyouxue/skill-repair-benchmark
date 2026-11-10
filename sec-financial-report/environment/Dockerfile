FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv wget unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /root
RUN pip3 install --break-system-packages pandas==2.3.3 rapidfuzz==3.14.3
COPY 2024-q1.zip 2024-q2.zip /root/archives/
RUN mkdir /root/2024-q1 /root/2024-q2     && unzip -q -j /root/archives/2024-q1.zip -d /root/2024-q1     && unzip -q -j /root/archives/2024-q2.zip -d /root/2024-q2
RUN ln -s /root/2024-q2 /root/2025-q2 && ln -s /root/2024-q2/INFOTABLE.tsv /root/INFOTABLE.tsv
