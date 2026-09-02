# Qbit Solo Miner

Private, permissionless Qbit solo mining on Umbrel. The app runs Qbit Core,
the official Qbit-adapted CKPool stack, and a local dashboard. SHA256d miners
connect to the Umbrel host on TCP port 3335, and block rewards are paid directly
to the configured external `qb1...` address.

The official
[`Qbit-Org/qbit-mining-bootstrap`](https://github.com/Qbit-Org/qbit-mining-bootstrap)
source is pinned and vendored. Automated verification checks it byte-for-byte,
while a scheduled workflow tests and publishes upstream updates before
advancing the Umbrel app version. See [`UPSTREAM.md`](UPSTREAM.md) for the exact
commit and update policy.
