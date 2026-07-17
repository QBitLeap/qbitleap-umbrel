# syntax=docker/dockerfile:1.7

ARG UBUNTU_VERSION=24.04

FROM ubuntu:${UBUNTU_VERSION} AS builder

ARG DEBIAN_FRONTEND=noninteractive
ARG QBIT_REPO=https://github.com/Qbit-Org/qbit.git
ARG QBIT_REF=main

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    git \
    libboost-dev \
    libevent-dev \
    libsqlite3-dev \
    libssl-dev \
    libzmq3-dev \
    pkg-config \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git clone --depth 1 --branch "${QBIT_REF}" "${QBIT_REPO}" qbit

WORKDIR /src/qbit

RUN cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_DAEMON=ON \
    -DBUILD_CLI=ON \
    -DBUILD_GUI=OFF \
    -DENABLE_WALLET=ON \
    -DENABLE_IPC=OFF \
    -DWITH_ZMQ=ON \
    -DBUILD_TESTS=OFF \
    -DBUILD_BENCH=OFF \
    -DBUILD_FUZZ_BINARY=OFF

RUN cmake --build build --target bitcoind bitcoin-cli -j"$(nproc)"

RUN install -m 0755 build/bin/qbitd /usr/local/bin/qbitd \
    && install -m 0755 build/bin/qbit-cli /usr/local/bin/qbit-cli

FROM ubuntu:${UBUNTU_VERSION}

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libevent-core-2.1-7t64 \
    libevent-extra-2.1-7t64 \
    libevent-pthreads-2.1-7t64 \
    libsqlite3-0 \
    libssl3 \
    libzmq5 \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/qbitd /usr/local/bin/qbitd
COPY --from=builder /usr/local/bin/qbit-cli /usr/local/bin/qbit-cli

VOLUME ["/data"]

EXPOSE 8352 8355

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/qbitd"]

CMD ["-datadir=/data", "-printtoconsole"]
