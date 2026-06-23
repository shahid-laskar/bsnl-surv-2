# Base image with FFmpeg + MediaMTX
FROM bluenviron/mediamtx:latest-ffmpeg

# Set timezone
ENV TZ=Asia/Kolkata

# Update Alpine packages and install dependencies
RUN apk update && apk add --no-cache \
    tzdata \
    curl \
    bash \
    kcat

# Copy your custom scripts into the container
COPY scripts/ /scripts/

# Make sure all shell scripts are executable
RUN chmod +x /scripts/*.sh

# Set working directory (optional, for convenience)
WORKDIR /scripts
