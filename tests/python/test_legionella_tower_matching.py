import unittest
from scripts.attach_legionella_tower_matches import extract_current_cluster, normalize_address


class LegionellaTowerMatchingTests(unittest.TestCase):
    def test_current_cluster_parser_preserves_zip_and_published_positive_addresses(self):
        text = """Legionnaires' Disease Cluster in the South Bronx
        parts of Melrose and Morrisania including ZIP codes 10451 and 10456.
        The following buildings have cooling towers that tested positive in a PCR test.
        820 Concourse Village West
        234 E. 149th St.
        1 E. 161st St.
        In addition to the PCR screening tests, another test follows.
        About Legionnaires' Disease"""
        cluster = extract_current_cluster(text)
        self.assertEqual(cluster['affected_zip_codes'], ['10451', '10456'])
        self.assertEqual(cluster['pcr_positive_building_addresses'], ['820 Concourse Village West', '234 E. 149th St.', '1 E. 161st St.'])
        self.assertEqual(cluster['status'], 'ACTIVE_INVESTIGATION')

    def test_address_normalization_is_exact_but_suffix_tolerant(self):
        self.assertEqual(normalize_address('234 E. 149th St.'), normalize_address('234 EAST 149TH STREET'))
        self.assertNotEqual(normalize_address('234 E. 149th St.'), normalize_address('236 EAST 149TH STREET'))


if __name__ == '__main__':
    unittest.main()
