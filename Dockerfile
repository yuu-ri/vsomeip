FROM ubuntu:jammy

SHELL ["/bin/bash", "-xec"]

# Install required tools and libraries
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install --no-install-recommends --yes \
        iputils-ping \
        net-tools \
        clang \
        cmake \
        g++ \
        googletest \
        libbenchmark-dev \
        libboost-filesystem-dev \
        libboost-system-dev \
        libboost-thread-dev \
        make \
        python3-pip \
        python3-venv && \
    python3 -m venv /venv && \
    /venv/bin/pip install gcovr && \
    apt-get autoremove --purge --yes && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Add virtual environment to PATH so it can be used easily
ENV PATH="/venv/bin:$PATH"

# Set environment variables for GTest
ENV GTEST_ROOT=/usr/src/googletest

