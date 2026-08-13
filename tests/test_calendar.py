import unittest
import generate_calendar as g

class Tests(unittest.TestCase):
    def test_home(self):
        self.assertTrue(g.is_home("Caledonia Steel Queens vs Solway Sharks Ladies"))
        self.assertFalse(g.is_home("Solway Sharks Ladies vs Caledonia Steel Queens"))
    def test_opponent(self):
        self.assertEqual(g.opponent("Caledonia Steel Queens vs Solway Sharks Ladies"), "Solway Sharks Ladies")
        self.assertEqual(g.opponent("Solway Sharks Ladies vs Caledonia Steel Queens"), "Solway Sharks Ladies")

if __name__ == '__main__': unittest.main()
