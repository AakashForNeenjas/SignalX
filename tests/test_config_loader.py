import os
import unittest

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import load_profiles, get_profile, DEFAULT_PROFILES


class TestConfigLoader(unittest.TestCase):
    def test_defaults_load(self):
        profiles = load_profiles(path="nonexistent_profiles.json")
        self.assertTrue(profiles)
        self.assertIn("sim", profiles)
        self.assertEqual(profiles.get("sim", {}).get("logging", {}).get("level"), "INFO")

    def test_get_profile_fallback(self):
        profiles = {"only": {"can": {}, "instruments": {}}}
        prof = get_profile("missing", profiles)
        self.assertEqual(prof, profiles["only"])

    def test_default_profiles_structure(self):
        self.assertIn("sim", DEFAULT_PROFILES)
        sim_profile = DEFAULT_PROFILES["sim"]
        self.assertIn("can", sim_profile)
        self.assertIn("instruments", sim_profile)
        self.assertIn("logging", sim_profile)


if __name__ == "__main__":
    unittest.main()
