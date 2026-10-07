import unittest

from engine import create_artifact


class LayeredArtifactEngineVectors(unittest.TestCase):
    def setUp(self):
        self.artifact = create_artifact("artifact-1", content={"value": "canon"})

    def layer(self, layer_id, value, *, parent_id=None, parent_digest=None):
        layer = self.artifact.propose_layer(layer_id, "REPLACE", {"value": value}, parent_id=parent_id, parent_digest=parent_digest)
        self.artifact.authorize_layer(layer.layer_id)
        return layer

    def test_lae_01_apply_fix_a(self):
        layer = self.layer("FIX-A", "a")
        result = self.artifact.apply_layer(layer.layer_id)
        self.assertEqual(result.status, "APPLIED")
        self.assertEqual(self.artifact.head_id, "FIX-A")

    def test_lae_02_apply_fix_b(self):
        a = self.layer("FIX-A", "a")
        self.assertEqual(self.artifact.apply_layer(a.layer_id).status, "APPLIED")
        b = self.layer("FIX-B", "b")
        self.assertEqual(self.artifact.apply_layer(b.layer_id).status, "APPLIED")
        self.assertEqual(self.artifact.head_id, "FIX-B")

    def test_lae_03_stale_reject_does_not_advance_head(self):
        a = self.layer("FIX-A", "a")
        self.assertEqual(self.artifact.apply_layer(a.layer_id).status, "APPLIED")
        c = self.layer("FIX-C", "c", parent_id="FIX-A", parent_digest=a.layer_digest)
        b = self.layer("FIX-B", "b")
        self.assertEqual(self.artifact.apply_layer(b.layer_id).status, "APPLIED")
        result = self.artifact.apply_layer(c.layer_id)
        self.assertEqual(result.status, "STALE_PARENT")
        self.assertEqual(self.artifact.head_id, "FIX-B")
        self.assertEqual(self.artifact.layers["FIX-C"].state, "STALE")

    def test_lae_04_rebase_creates_new_identity(self):
        a = self.layer("FIX-A", "a")
        self.artifact.apply_layer(a.layer_id)
        c = self.layer("FIX-C", "c", parent_id="FIX-A", parent_digest=a.layer_digest)
        b = self.layer("FIX-B", "b")
        self.artifact.apply_layer(b.layer_id)
        self.assertEqual(self.artifact.apply_layer(c.layer_id).status, "STALE_PARENT")
        rebased = self.artifact.rebase("FIX-C", "FIX-C-R1")
        self.assertEqual(rebased.parent_id, "FIX-B")
        self.assertNotEqual(rebased.layer_id, c.layer_id)
        self.assertEqual(self.artifact.layers["FIX-C"].state, "STALE")

    def test_lae_05_lineage_snapshot_and_receipt(self):
        a = self.layer("FIX-A", "a")
        self.artifact.apply_layer(a.layer_id)
        b = self.layer("FIX-B", "b")
        self.artifact.apply_layer(b.layer_id)
        c = self.layer("FIX-C", "c", parent_id="FIX-A", parent_digest=a.layer_digest)
        self.assertEqual(self.artifact.apply_layer(c.layer_id).status, "STALE_PARENT")
        r1 = self.artifact.rebase("FIX-C", "FIX-C-R1")
        self.artifact.authorize_layer(r1.layer_id)
        result = self.artifact.apply_layer(r1.layer_id)
        self.assertEqual(result.status, "APPLIED")
        self.assertEqual(self.artifact.snapshot.lineage, ("CANON", "FIX-A", "FIX-B", "FIX-C-R1"))
        self.assertEqual(self.artifact.snapshot.content["value"], "c")
        self.assertTrue(result.receipt.receipt_id.startswith("sha256:"))

    def test_lae_06_idempotent_apply(self):
        layer = self.layer("FIX-A", "a")
        self.assertEqual(self.artifact.apply_layer(layer.layer_id).status, "APPLIED")
        receipt_count = len(self.artifact.receipts)
        self.assertEqual(self.artifact.apply_layer(layer.layer_id).status, "ALREADY_APPLIED")
        self.assertEqual(len(self.artifact.receipts), receipt_count)

    def test_snapshot_is_deterministic_for_same_resolved_inputs(self):
        layer = self.layer("FIX-A", "a")
        self.assertEqual(self.artifact.apply_layer(layer.layer_id).status, "APPLIED")
        first = self.artifact.materialize_snapshot()
        second = self.artifact.materialize_snapshot()
        self.assertEqual(first.snapshot_digest, second.snapshot_digest)
        self.assertEqual(first.content, second.content)

    def test_lae_07_failure_does_not_advance_head(self):
        layer = self.layer("FIX-A", "a")
        result = self.artifact.apply_layer(layer.layer_id, simulate_failure=True)
        self.assertEqual(result.status, "FAILED")
        self.assertIsNone(self.artifact.head_id)
        self.assertEqual(self.artifact.snapshot.head_id, None)


if __name__ == "__main__":
    unittest.main()
