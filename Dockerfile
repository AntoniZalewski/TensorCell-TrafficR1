# Base image with CUDA devel support
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-devel

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# --- FIX: Build CityFlow from source ---
# CityFlow is not available via simple pip install on this architecture.
# We clone the source and compile it using the installed cmake/g++.
RUN git clone https://github.com/cityflow-project/CityFlow.git /tmp/CityFlow && \
    pip install /tmp/CityFlow && \
    rm -rf /tmp/CityFlow

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Note: We do NOT clone the repo here anymore because we mount the local directory to /app
# This ensures we always run the latest local code.