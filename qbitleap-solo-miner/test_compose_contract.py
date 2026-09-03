import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
MANIFEST = (ROOT / "umbrel-app.yml").read_text(encoding="utf-8")
STORE = (ROOT.parent / "umbrel-app-store.yml").read_text(encoding="utf-8")


class ComposeContractTests(unittest.TestCase):
    def test_all_release_images_use_manifest_version(self):
        version = re.search(r'^version: "([^"]+)"$', MANIFEST, re.MULTILINE).group(1)
        image_versions = re.findall(r"image: ghcr\.io/qbitleap/qbit-solo-[^:]+:([^\s]+)", COMPOSE)
        self.assertTrue(image_versions)
        self.assertEqual(set(image_versions), {version})

    def test_ckpool_uses_production_permissionless_policy(self):
        self.assertIn('CKPOOL_MINDIFF: "1024"', COMPOSE)
        self.assertIn('CKPOOL_STARTDIFF: "8192"', COMPOSE)
        self.assertIn('CKPOOL_NON_TEST_READINESS_GATE: "1"', COMPOSE)
        self.assertIn('CKPOOL_REQUIRE_P2MR_PAYOUT: "1"', COMPOSE)
        self.assertIn("exec /usr/local/bin/start-ckpool.sh", COMPOSE)

    def test_stratum_and_qbit_p2p_are_published_to_the_host(self):
        published = re.findall(r'^\s+- "([0-9]+):([0-9]+)"$', COMPOSE, re.MULTILINE)
        self.assertEqual(published, [("8355", "8355"), ("3335", "3335")])

    def test_public_stratum_uses_worker_compatibility_router(self):
        self.assertIn("command: [python, /app/router.py]", COMPOSE)
        self.assertIn("CKPOOL_BACKEND_PORT: \"3333\"", COMPOSE)
        self.assertIn("MINER_ADDRESS_FILE: /config/miner_address", COMPOSE)

    def test_dashboard_and_manifest_ports_match(self):
        manifest_port = re.search(r"^port: ([0-9]+)$", MANIFEST, re.MULTILINE).group(1)
        proxy_port = re.search(r"APP_PORT: ([0-9]+)", COMPOSE).group(1)
        self.assertEqual(manifest_port, proxy_port)

    def test_app_id_is_namespaced_to_the_community_store(self):
        store_id = re.search(r"^id: ([^\s]+)$", STORE, re.MULTILINE).group(1)
        app_id = re.search(r"^id: ([^\s]+)$", MANIFEST, re.MULTILINE).group(1)
        self.assertTrue(app_id.startswith(f"{store_id}-"))
        self.assertEqual(ROOT.name, app_id)

    def test_manifest_declares_the_published_icon(self):
        self.assertIn(
            "icon: https://raw.githubusercontent.com/QBitLeap/qbitleap-umbrel/main/"
            "qbitleap-solo-miner/icon.svg",
            MANIFEST,
        )


if __name__ == "__main__":
    unittest.main()
