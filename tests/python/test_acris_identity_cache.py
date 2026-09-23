import copy
import unittest
from unittest.mock import Mock
from scripts.towersignal.acris import tower_bbl_hash
from scripts.towersignal.acris_identity_cache import ensure_alignment, graph_digest, property_targets


class AcrisIdentityCacheTests(unittest.TestCase):
    def systems(self):
        return [{"system_id": "S1", "bin": "1089723", "bbl": "1011717513", "bbl_aliases": ["1011710154", "1011717513"], "address": "400 WEST 61ST STREET"}]

    def cache(self, systems):
        targets = property_targets(systems)
        return {"tower_bbl_universe": {"sha256": tower_bbl_hash(targets)}, "mapping_property_graph_sha256": graph_digest(targets)}

    def test_aligned_cache_is_reused_without_network(self):
        systems = self.systems(); cache = self.cache(systems); builder = Mock()
        result, rebuilt = ensure_alignment(cache, systems, builder=builder)
        self.assertIs(result, cache)
        self.assertFalse(rebuilt)
        builder.assert_not_called()

    def test_changed_aliases_with_equal_counts_invalidate_cache(self):
        systems = self.systems(); cache = self.cache(systems)
        systems[0]["bbl_aliases"][0] = "1011710155"
        builder = Mock(return_value=self.cache(systems))
        result, rebuilt = ensure_alignment(cache, systems, builder=builder)
        self.assertTrue(rebuilt)
        builder.assert_called_once()
        self.assertNotEqual(result["mapping_property_graph_sha256"], cache["mapping_property_graph_sha256"])

    def test_changed_properties_with_equal_counts_invalidate_cache(self):
        systems = self.systems(); cache = self.cache(systems)
        systems[0]["bbl"] = "1011717514"
        builder = Mock(return_value=self.cache(systems))
        _, rebuilt = ensure_alignment(cache, systems, builder=builder)
        self.assertTrue(rebuilt)
        self.assertEqual(builder.call_args.args[0], {"1011717514"})

    def test_repeated_property_preserves_all_confirmed_aliases(self):
        systems = self.systems()
        systems.append({**systems[0], "system_id": "S2", "bbl_aliases": ["1011710155", "1011717513"]})
        targets = property_targets(systems)
        self.assertEqual(targets["1011717513"]["bbl_aliases"], ["1011710154", "1011710155", "1011717513"])
        self.assertEqual(targets, property_targets(list(reversed(systems))))

    def test_failed_refresh_does_not_modify_previous_cache(self):
        systems = self.systems(); cache = self.cache(systems); old = copy.deepcopy(cache)
        systems[0]["bbl_aliases"].append("1011710156")
        with self.assertRaisesRegex(RuntimeError, "source unavailable"):
            ensure_alignment(cache, systems, builder=Mock(side_effect=RuntimeError("source unavailable")))
        self.assertEqual(cache, old)

    def test_mismatched_rebuilt_universe_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            ensure_alignment(None, self.systems(), builder=Mock(return_value={"tower_bbl_universe": {"sha256": "wrong"}}))


if __name__ == "__main__":
    unittest.main()
