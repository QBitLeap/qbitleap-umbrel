# syntax=docker/dockerfile:1.7

ARG UBUNTU_VERSION=24.04

FROM ubuntu:${UBUNTU_VERSION} AS build

ARG DEBIAN_FRONTEND=noninteractive
ARG CKPOOL_GIT_URL=https://bitbucket.org/ckolivas/ckpool.git
ARG CKPOOL_GIT_REF=88e99e0b6fc7e28796c8450b42fa00070b66c6e3

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    build-essential \
    ca-certificates \
    git \
    libcurl4-openssl-dev \
    libjansson-dev \
    libtool \
    libzmq3-dev \
    pkgconf \
    yasm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git clone --depth 1 https://github.com/Qbit-Org/qbit-mining-bootstrap.git bootstrap

WORKDIR /src/ckpool

RUN git init . \
    && git remote add origin "${CKPOOL_GIT_URL}" \
    && git fetch --depth 1 origin "${CKPOOL_GIT_REF}" \
    && git checkout FETCH_HEAD

RUN git apply /src/bootstrap/docker/ckpool/qbit-regtest.patch \
    && git apply /src/bootstrap/docker/ckpool/qbit-signet-gbt.patch

RUN ./autogen.sh \
    && ./configure \
    && make -C src/jansson-2.14/src -j"$(nproc)" \
    && make -C src -j"$(nproc)" ckpool

FROM ubuntu:${UBUNTU_VERSION}

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    libcurl4 \
    libjansson4 \
    libzmq5 \
    python3 \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/ckpool/src/ckpool /usr/local/bin/ckpool
COPY --from=build /src/bootstrap/docker/ckpool/ckpool-version-mask.py /usr/local/bin/ckpool-version-mask
COPY --from=build /src/bootstrap/docker/ckpool/qbit-ckpool-preflight.py /usr/local/bin/qbit-ckpool-preflight
COPY --from=build /src/bootstrap/docker/ckpool/start-ckpool.sh /usr/local/bin/start-ckpool.sh

RUN chmod +x \
    /usr/local/bin/ckpool-version-mask \
    /usr/local/bin/qbit-ckpool-preflight \
    /usr/local/bin/start-ckpool.sh

EXPOSE 3333

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/local/bin/start-ckpool.sh"]
