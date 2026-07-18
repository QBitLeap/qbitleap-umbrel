#!/usr/bin/env bash
set -euo pipefail

CREDENTIALS_FILE="/config/rpc_credentials"
MINER_ADDRESS_FILE="/config/miner_address"
UPSTREAM_START_SCRIPT="/usr/local/bin/start-ckpool-upstream.sh"

if [[ ! -r "${CREDENTIALS_FILE}" ]]; then
    echo "CKPool error: RPC credentials file is missing or unreadable: ${CREDENTIALS_FILE}" >&2
    exit 1
fi

RPC_CREDENTIALS="$(tr -d '\r\n' < "${CREDENTIALS_FILE}")"

if [[ "${RPC_CREDENTIALS}" != *:* ]]; then
    echo "CKPool error: RPC credentials file must use username:password format" >&2
    exit 1
fi

QBIT_RPC_USER="${RPC_CREDENTIALS%%:*}"
QBIT_RPC_PASSWORD="${RPC_CREDENTIALS#*:}"

if [[ -z "${QBIT_RPC_USER}" ]]; then
    echo "CKPool error: RPC username is empty" >&2
    exit 1
fi

if [[ -z "${QBIT_RPC_PASSWORD}" ]]; then
    echo "CKPool error: RPC password is empty" >&2
    exit 1
fi

if [[ ! -r "${MINER_ADDRESS_FILE}" ]]; then
    echo "CKPool waiting: payout address has not been configured yet" >&2
    exit 1
fi

QBIT_MINER_ADDRESS="$(tr -d '\r\n' < "${MINER_ADDRESS_FILE}")"

if [[ -z "${QBIT_MINER_ADDRESS}" ]]; then
    echo "CKPool waiting: payout address is empty" >&2
    exit 1
fi

if [[ "${QBIT_MINER_ADDRESS}" != qb1* ]]; then
    echo "CKPool error: mainnet payout address must begin with qb1" >&2
    exit 1
fi

if [[ ! -x "${UPSTREAM_START_SCRIPT}" ]]; then
    echo "CKPool error: upstream startup script is missing: ${UPSTREAM_START_SCRIPT}" >&2
    exit 1
fi

export QBIT_RPC_USER
export QBIT_RPC_PASSWORD
export QBIT_MINER_ADDRESS

export QBIT_RPC_HOST="${QBIT_RPC_HOST:-qbitd}"
export QBIT_RPC_PORT="${QBIT_RPC_PORT:-8352}"
export QBIT_CHAIN="${QBIT_CHAIN:-mainnet}"

exec "${UPSTREAM_START_SCRIPT}"
