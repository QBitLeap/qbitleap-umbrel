# Qbit Solo

Qbit Solo is a focused Umbrel application for permissionless Qbit solo mining.

## Current App

### Qbit Solo

A native Umbrel application for running:

- Qbit Core
- Permissionless CKPool
- Solo mining infrastructure
- Local Stratum endpoint on TCP port 3335

## Project Goals

- One-click installation on Umbrel
- External payout address support
- Persistent blockchain and configuration storage
- Integrated dashboard
- Accurate local miner telemetry and permanent block history
- No manual Docker management after installation

Qbit Solo uses a pinned, verified snapshot of the official
[`Qbit-Org/qbit-mining-bootstrap`](https://github.com/Qbit-Org/qbit-mining-bootstrap)
repository. Its scheduled updater publishes all required images before exposing
a new Umbrel app version. The exact pin and integrity policy are documented in
the repository's [`UPSTREAM.md`](../UPSTREAM.md).
