# Qbit Solo Miner

Qbit Solo Miner is a focused Umbrel application for permissionless Qbit solo mining.

## Current App

### Qbit Solo Miner

A native Umbrel application for running:

- Qbit Core
- Permissionless CKPool
- Solo mining infrastructure
- Local Stratum endpoint on TCP port 3335

## Connecting miners

Local miners should connect to:

```text
stratum+tcp://<UMBREL-LAN-IP>:3335
```

For rented hashpower, forward a public router TCP port to port `3335` on the
Umbrel host, then configure the provider with:

```text
stratum+tcp://<PUBLIC-IP-OR-DNS-NAME>:<FORWARDED-PORT>
```

The provider's worker name may be simple (for example, `rental-1`). Qbit Solo
automatically binds authorization and submitted shares to the payout address
saved in the dashboard. Opening a router port exposes a mining service to the
Internet, so restrict the source addresses in the router firewall when the
provider publishes its outbound IP ranges.

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
