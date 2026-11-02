# ==============================================================================
# ArchGen - Headless Blender Generation Worker
# ==============================================================================
# Base image: Ubuntu 22.04 LTS with Headless Blender 3.6 LTS / 4.x
# Prepared for background 3D architecture generation tasks.
# ==============================================================================

FROM ubuntu:22.04

# Prevent interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV BLENDER_MAJOR=3.6
ENV BLENDER_VERSION=3.6.14
ENV BLENDER_TAR_URL=https://ftp.nluug.nl/pub/graphics/blender/release/Blender${BLENDER_MAJOR}/blender-${BLENDER_VERSION}-linux-x64.tar.xz

# Install essential system dependencies and software rendering libs (Mesa/OpenGL/X11)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    tar \
    xz-utils \
    bzip2 \
    ca-certificates \
    python3 \
    python3-pip \
    libglu1-mesa \
    libgl1-mesa-dri \
    libgl1-mesa-glx \
    libxi6 \
    libxrender1 \
    libxxf86vm1 \
    libxfixes3 \
    libxkbcommon0 \
    libsm6 \
    libfontconfig1 \
    libxcursor1 \
    libxinerama1 \
    libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

# Download and install Blender
WORKDIR /opt
RUN curl -sSL ${BLENDER_TAR_URL} -o blender.tar.xz && \
    tar -xf blender.tar.xz && \
    rm blender.tar.xz && \
    mv blender-${BLENDER_VERSION}-linux-x64 blender

# Create symlink for global blender command
ENV PATH="/opt/blender:${PATH}"

# Setup ArchGen workspace directory
WORKDIR /app/blender

# Copy blender directory structure and scripts
COPY . /app/blender/

# Install worker dependencies
RUN pip3 install --no-cache-dir flask flask-cors boto3 requests

# Blender runs generation scripts with its own Python, separate from python3
# above. Its S3 resolver needs boto3 too when an asset is not cached locally.
RUN blender_python="$(find /opt/blender -path '*/python/bin/python3.*' -type f | sort | head -n 1)" && \
    test -n "$blender_python" && \
    "$blender_python" -m ensurepip && \
    "$blender_python" -m pip install --no-cache-dir boto3 && \
    "$blender_python" -c "import boto3; import botocore; import s3transfer" && \
    blender --background --factory-startup --python-exit-code 1 \
        --python-expr "import boto3; import botocore; print('[BUILD] Blender S3 dependencies available')"

# Ensure output and input directories exist
RUN mkdir -p /app/blender/output /app/blender/input

# Expose worker API port
EXPOSE 5001

# Run HTTP worker microservice
CMD ["python3", "worker_server.py"]

