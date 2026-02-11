FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

# Install system dependencies
# ffmpeg: Required for video processing
# libpq-dev: Required for building psycopg2 (if needed) and other postgres tools
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends ffmpeg libpq-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv for Python dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Note: comskip is omitted to keep the dev environment lightweight and standard.
# If required, it can be installed manually or added here later.
