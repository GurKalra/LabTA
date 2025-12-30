FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    openjdk-17-jdk \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Security: Run as non-root
RUN useradd -m student
USER student
WORKDIR /app