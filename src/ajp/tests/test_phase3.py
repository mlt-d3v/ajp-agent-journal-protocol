"""Phase 3 tests - Security Hardening."""
import sys
import unittest

sys.path.insert(0, "/Users/michaelthomas/.hermes/skills/ajp-agent-journal-protocol/src")

from ajp.core.anchoring import AnchorBackend, MerkleAnchoringService
from ajp.core.entry import EventType, JournalEntry
from ajp.security.hsm import CloudHSM, KeyState, KeyType, SoftwareHSM
from ajp.security.orchestrator import AuditEvent, SecurityOrchestrator
from ajp.security.vault_client import AuthMethod, MockVaultAdapter, VaultClient


class TestVaultClient(unittest.TestCase):
    def test_connect(self):
        vc = VaultClient(token="test-token")
        self.assertTrue(vc.connect())
        self.assertTrue(vc.is_connected)

    def test_write_and_read(self):
        vc = VaultClient(token="test")
        vc.connect()
        vc.write("secret/test", {"key": "val"})
        result = vc.read("secret/test")
        self.assertEqual(result["key"], "val")

    def test_delete(self):
        vc = VaultClient(token="test")
        vc.connect()
        vc.write("secret/test", {"key": "val"})
        self.assertTrue(vc.delete("secret/test"))
        self.assertIsNone(vc.read("secret/test"))

    def test_list_keys(self):
        vc = VaultClient(token="test")
        vc.connect()
        vc.write("a", {"x": 1})
        vc.write("b", {"x": 2})
        keys = vc.list_keys()
        self.assertIn("a", keys)
        self.assertIn("b", keys)

    def test_renew_lease(self):
        vc = VaultClient(token="test")
        vc.connect()
        self.assertTrue(vc.renew_lease())

    def test_get_token(self):
        vc = VaultClient(token="my-token")
        self.assertEqual(vc.get_token(), "my-token")

    def test_auth_methods(self):
        vc = VaultClient(auth_method=AuthMethod.APPROLE)
        self.assertEqual(vc.auth_method, AuthMethod.APPROLE)

    def test_mock_vault_standalone(self):
        mv = MockVaultAdapter()
        mv.store("path", {"data": "val"})
        self.assertEqual(mv.retrieve("path")["data"], "val")
        self.assertTrue(mv.delete("path"))


class TestSoftwareHSM(unittest.TestCase):
    def test_generate_key(self):
        hsm = SoftwareHSM()
        self.assertTrue(hsm.generate_key("key1", KeyType.ED25519))
        self.assertEqual(hsm.get_key_state("key1"), KeyState.ACTIVE)

    def test_sign_and_verify(self):
        hsm = SoftwareHSM()
        hsm.generate_key("key1")
        data = b"test data"
        sig = hsm.sign("key1", data)
        self.assertIsNotNone(sig)
        self.assertTrue(hsm.verify("key1", data, sig))

    def test_sign_fail_unknown_key(self):
        hsm = SoftwareHSM()
        self.assertIsNone(hsm.sign("unknown", b"data"))

    def test_rotate_key(self):
        hsm = SoftwareHSM()
        hsm.generate_key("key1")
        self.assertTrue(hsm.rotate_key("key1"))
        self.assertEqual(hsm.get_key_state("key1"), KeyState.ROTATED)

    def test_destroy_key(self):
        hsm = SoftwareHSM()
        hsm.generate_key("key1")
        self.assertTrue(hsm.destroy_key("key1"))
        self.assertEqual(hsm.get_key_state("key1"), KeyState.DESTROYED)
        self.assertIsNone(hsm.sign("key1", b"data"))

    def test_cloud_hsm(self):
        chsm = CloudHSM(provider="aws", region="us-west-2")
        chsm.generate_key("cloud_key", KeyType.RSA_2048)
        self.assertEqual(chsm.get_key_state("cloud_key"), KeyState.ACTIVE)

    def test_key_types(self):
        hsm = SoftwareHSM()
        for kt in KeyType:
            hsm.generate_key(f"key_{kt.value}", kt)
            self.assertEqual(hsm.get_key_state(f"key_{kt.value}"), KeyState.ACTIVE)

    def test_verify_wrong_data(self):
        hsm = SoftwareHSM()
        hsm.generate_key("key1")
        sig = hsm.sign("key1", b"original")
        self.assertFalse(hsm.verify("key1", b"tampered", sig))


class TestAnchoring(unittest.TestCase):
    def test_anchor_local(self):
        svc = MerkleAnchoringService(AnchorBackend.LOCAL)
        record = svc.anchor_root("abc123")
        self.assertIsNotNone(record)
        self.assertTrue(record.verified)

    def test_verify_root(self):
        svc = MerkleAnchoringService(AnchorBackend.LOCAL)
        svc.anchor_root("root1")
        self.assertTrue(svc.verify_root("root1"))
        self.assertFalse(svc.verify_root("unknown"))

    def test_github_anchor(self):
        svc = MerkleAnchoringService(AnchorBackend.GITHUB)
        record = svc.anchor_root("gh_root")
        self.assertTrue(record.verified)

    def test_ipfs_anchor(self):
        svc = MerkleAnchoringService(AnchorBackend.IPFS)
        record = svc.anchor_root("ipfs_root")
        self.assertTrue(record.verified)

    def test_blockchain_anchor(self):
        svc = MerkleAnchoringService(AnchorBackend.BLOCKCHAIN)
        record = svc.anchor_root("bc_root")
        self.assertFalse(record.verified)

    def test_get_anchor(self):
        svc = MerkleAnchoringService()
        record = svc.anchor_root("test")
        found = svc.get_anchor(record.anchor_id)
        self.assertEqual(found.root_hash, "test")

    def test_history(self):
        svc = MerkleAnchoringService()
        svc.anchor_root("r1")
        svc.anchor_root("r2")
        self.assertEqual(len(svc.get_history()), 2)
        self.assertEqual(len(svc.get_history("r1")), 1)

    def test_stats(self):
        svc = MerkleAnchoringService()
        svc.anchor_root("s1")
        svc.anchor_root("s2")
        stats = svc.get_stats()
        self.assertEqual(stats["total_anchors"], 2)

    def test_multiple_backends(self):
        for backend in AnchorBackend:
            svc = MerkleAnchoringService(backend)
            svc.anchor_root(f"root_{backend.value}")


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.vault = VaultClient(token="test")
        self.vault.connect()
        self.orch = SecurityOrchestrator(vault=self.vault)

    def test_provision_agent(self):
        self.assertTrue(self.orch.provision_agent("agent1"))

    def test_sign_entry(self):
        self.orch.provision_agent("agent1")
        entry = JournalEntry(agent_id="agent1", event_type=EventType.THOUGHT, entry_data={"msg": "test"})
        entry.compute_hash()
        self.assertTrue(self.orch.sign_entry("agent1", entry))
        self.assertIsNotNone(entry.signature)

    def test_verify_entry(self):
        self.orch.provision_agent("agent1")
        entry = JournalEntry(agent_id="agent1", event_type=EventType.THOUGHT, entry_data={"msg": "test"})
        entry.compute_hash()
        self.orch.sign_entry("agent1", entry)
        self.assertTrue(self.orch.verify_entry("agent1", entry))

    def test_rotate_key(self):
        self.orch.provision_agent("agent1")
        self.assertTrue(self.orch.rotate_agent_key("agent1"))

    def test_anchor_root(self):
        self.assertTrue(self.orch.anchor_merkle_root("test_root"))

    def test_audit_log(self):
        self.orch.provision_agent("agent1")
        logs = self.orch.get_audit_log()
        self.assertGreater(len(logs), 0)
        key_logs = self.orch.get_audit_log(AuditEvent.KEY_GENERATED)
        self.assertGreater(len(key_logs), 0)

    def test_full_workflow(self):
        self.orch.provision_agent("agent1")
        entry = JournalEntry(agent_id="agent1", event_type=EventType.COMMIT, entry_data={"action": "deploy"})
        entry.compute_hash()
        self.orch.sign_entry("agent1", entry)
        self.assertTrue(self.orch.verify_entry("agent1", entry))
        self.orch.anchor_merkle_root(entry.entry_hash)

    def test_penetration_rbac_bypass(self):
        self.orch.provision_agent("agent1")
        entry = JournalEntry(agent_id="agent1", event_type=EventType.THOUGHT, entry_data={})
        entry.compute_hash()
        self.assertFalse(self.orch.sign_entry("unknown_agent", entry))

    def test_penetration_chain_tamper(self):
        self.orch.provision_agent("agent1")
        entry = JournalEntry(agent_id="agent1", event_type=EventType.THOUGHT, entry_data={})
        entry.compute_hash()
        self.orch.sign_entry("agent1", entry)
        entry.entry_data["msg"] = "tampered"
        entry.compute_hash()
        self.assertFalse(self.orch.verify_entry("agent1", entry))

    def test_penetration_key_revocation(self):
        self.orch.provision_agent("agent1")
        entry = JournalEntry(agent_id="agent1", event_type=EventType.THOUGHT, entry_data={})
        entry.compute_hash()
        self.orch.sign_entry("agent1", entry)
        self.orch.hsm.destroy_key(self.orch._agent_keys["agent1"])
        self.assertIsNone(self.orch.hsm.sign(self.orch._agent_keys["agent1"], b"data"))


if __name__ == "__main__":
    unittest.main()
