from unittest import TestCase
from unittest.mock import Mock
from vision import Vision
import numpy as np

class VisionTest(TestCase):

    def setUp(self):
        self.vision = Vision()

    def test_finds_finished_mission(self):
        screenshot = self.vision.get_image('tests/screens/round-finished-missions.png')
        match = self.vision.find_template('tap-to-continue', screenshot)
        self.assertEqual(np.shape(match)[1], 1)

    def test_finds_next_button(self):
        screenshot = self.vision.get_image('tests/screens/round-finished-results.png')
        match = self.vision.find_template('next-button', screenshot)
        self.assertEqual(np.shape(match)[1], 1)

    def test_finds_round_starting_indicator(self):
        screenshot = self.vision.get_image('tests/screens/round-started.png')
        match = self.vision.find_template('bison-health-bar', screenshot)
        self.assertEqual(np.shape(match)[1], 1)

    def test_finds_bison_head(self):
        screenshot = self.vision.get_image('tests/screens/round-started.png')
        match = self.vision.find_template('bison-head', screenshot)
        self.assertEqual(np.shape(match)[1], 1)

    def test_finds_pineapple_head(self):
        screenshot = self.vision.get_image('tests/screens/round-in-progress-pineapple-spank.png')
        match = self.vision.scaled_find_template('left-goalpost', screenshot, threshold=0.75, scales=[1.1, 1.0, 0.99, 0.98, 0.97, 0.96, 0.95])
        self.assertGreaterEqual(np.shape(match)[1], 1)

    def test_finds_full_rocket(self):
        screenshot = self.vision.get_image('tests/screens/round-in-progress.png')
        match = self.vision.find_template('full-rocket', screenshot, threshold=0.9)
        self.assertGreaterEqual(np.shape(match)[1], 1)

    def test_finds_filled_with_goodies(self):
        screenshot = self.vision.get_image('tests/screens/pinata.png')
        match = self.vision.find_template('filled-with-goodies', screenshot, threshold=0.9)
        self.assertGreaterEqual(np.shape(match)[1], 1)

    def test_finds_cancel_button(self):
        screenshot = self.vision.get_image('tests/screens/pinata.png')
        match = self.vision.find_template('cancel-button', screenshot, threshold=0.9)
        self.assertGreaterEqual(np.shape(match)[1], 1)

    def test_finds_left_goalpost_with_beaster_bunny(self):
        screenshot = self.vision.get_image('tests/screens/round-start-beaster-bunny.png')
        match = self.vision.find_template('left-goalpost', screenshot, threshold=0.99)
        self.assertEqual(np.shape(match)[1], 1)

    def test_detects_scale_on_new_screenshot(self):
        screenshot = self.vision.get_image('tests/new_screens_1/ground-started.png')
        detected_scale = self.vision.detect_scale(screenshot)
        self.assertIsNotNone(detected_scale)
        self.assertAlmostEqual(detected_scale, 0.82, places=2)

    def test_finds_bison_head_on_scaled_screenshot(self):
        screenshot = self.vision.get_image('tests/new_screens_1/ground-started.png')
        detected_scale = self.vision.detect_scale(screenshot)
        self.vision.set_scale(detected_scale)
        match = self.vision.find_template('bison-head', screenshot, threshold=0.8)
        self.assertGreaterEqual(np.shape(match)[1], 1)
        self.vision.set_scale(1.0)


