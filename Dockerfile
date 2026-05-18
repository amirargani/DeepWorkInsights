# linux/amd64 (x86_64 emulation via Rosetta 2 on Apple Silicon) — required because
# scikit-learn 0.24.2 (needed by auto-sklearn 0.15.0) has no pre-built aarch64 wheel
# and its Cython-generated C code cannot be compiled with modern GCC.
# Python 3.9 on Debian Bullseye (GCC 10, openjdk-11) — the oldest env with pre-built
# manylinux wheels for scikit-learn 0.24.2 that is still supported by auto-sklearn 0.15.0.
FROM --platform=linux/amd64 python:3.9-slim-bullseye

# System packages:
#   build-essential, swig  — compile pyrfr / SMAC3 C extensions (auto-sklearn)
#   openjdk-11-jre-headless — JVM for H2O AutoML (Java 8+ required; 11 is on Bullseye)
#   libopenblas-dev, gfortran — BLAS/LAPACK for scipy/numpy
#   cmake — required by some SMAC3 / ConfigSpace build backends
#   git, curl — general utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    swig \
    openjdk-11-jre-headless \
    libopenblas-dev \
    gfortran \
    cmake \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/lib/jvm/java-11-openjdk-* /usr/lib/jvm/java-11-openjdk

# JAVA_HOME via symlink — works without hardcoding the arch suffix in the path
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"

WORKDIR /app

# Upgrade pip and build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Step 1: install numpy and scipy first (auto-sklearn setup.py imports them)
RUN pip install --no-cache-dir "numpy>=1.21,<2.0" "scipy>=1.7"

# Step 2: scikit-learn 0.24.2 — pre-built manylinux wheel exists for Python 3.9 x86_64
#         (no source compilation needed on this platform)
RUN pip install --no-cache-dir "scikit-learn==0.24.2"

# Step 3: install auto-sklearn (compiles pyrfr via swig — takes ~3–5 min)
RUN pip install --no-cache-dir "auto-sklearn==0.15.0"

# Step 4: install H2O and pandas (no compilation needed — pure Python / wheels)
RUN pip install --no-cache-dir h2o pandas openpyxl requests

# Step 5: pin setuptools<71 so that 'import pkg_resources' still works at runtime.
# auto-sklearn 0.15.0's __init__.py does "import pkg_resources" which was removed as
# a top-level module in setuptools >= 71.  This must come AFTER auto-sklearn is built
# so that the build process itself can use the modern setuptools.
RUN pip install --no-cache-dir "setuptools<71"

# Project files are mounted via docker-compose volume, not copied into the image,
# so the container always reflects the latest changes on the host filesystem.
