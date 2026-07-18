#!/bin/sh
set -eu

CONFIG_DIR="/config"
CREDENTIALS_FILE="${CONFIG_DIR}/rpc_credentials"
QBIT_CONFIG="${CONFIG_DIR}/qbit.conf"

mkdir -p "${CONFIG_DIR}"

if [ ! -f "${CREDENTIALS_FILE}" ]; then
  RPC_PASSWORD="$(head -c 32 /dev/urandom | base64 | tr -d '\n')"
  printf 'qbitleap:%s\n' "${RPC_PASSWORD}" > "${CREDENTIALS_FILE}"
  chmod 600 "${CREDENTIALS_FILE}"
fi

RPC_USER="$(cut -d: -f1 "${CREDENTIALS_FILE}")"
RPC_PASSWORD="$(cut -d: -f2- "${CREDENTIALS_FILE}")"

cat > "${QBIT_CONFIG}" <<EOF
server=1
rpcbind=0.0.0.0
rpcallowip=0.0.0.0/0
rpcuser=${RPC_USER}
rpcpassword=${RPC_PASSWORD}
printtoconsole=1
dbcache=512
EOF

chmod 600 "${QBIT_CONFIG}"
