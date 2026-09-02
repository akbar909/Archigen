# ==============================================================================
# ArchGen - Headless Blender Generation Worker
# ==============================================================================
# Base image: Ubuntu 22.04 LTS with Headless Blender 3.6 LTS / 4.x
# Prepared for background 3D architecture generation tasks.
# ==============================================================================

FROM ubuntu:22.04

# Prevent interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive
ENV BLENDER_MAJOR=3.6
ENV BLENDER_VERSION=3.6.14
ENV BLENDER_TAR_URL=https://download.blender.org/release/Blender${BLENDER_MAJOR}/blender-${BLENDER_VERSION}-linux-x64.tar.xz

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
    libxxf86vm \
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
RUN wget -q ${BLENDER_TAR_URL} -O blender.tar.xz && \
    tar -xf blender.tar.xz && \
    rm blender.tar.xz && \
    mv blender-${BLENDER_VERSION}-linux-x64 blender

# Create symlink for global blender command
ENV PATH="/opt/blender:${PATH}"

# Setup ArchGen workspace directory
WORKDIR /app/blender

# Copy blender directory structure and scripts
COPY . /app/blender/

# Ensure output directory exists
RUN mkdir -p /app/blender/output /app/blender/input

# Default command: Runs sample house generation in headless background mode
CMD ["blender", "--background", "--python", "scripts/generate_house.py", "--", "--input", "input/sample_house_layout.json", "--output", "output/generated_house.glb"]
