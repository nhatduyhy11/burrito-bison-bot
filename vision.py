import cv2
from mss import mss
from PIL import Image
import numpy as np
import time

class Vision:
    def __init__(self):
        self.static_templates = {
            'left-goalpost': 'assets/left-goalpost.png',
            'bison-head': 'assets/bison-head.png',
            'pineapple-head': 'assets/pineapple-head.png',
            'bison-health-bar': 'assets/bison-health-bar.png',
            'pineapple-health-bar': 'assets/pineapple-health-bar.png',
            'cancel-button': 'assets/cancel-button.png',
            'filled-with-goodies': 'assets/filled-with-goodies.png',
            'next-button': 'assets/next-button.png',
            'tap-to-continue': 'assets/tap-to-continue.png',
            'unlocked': 'assets/unlocked.png',
            'full-rocket': 'assets/full-rocket.png'
        }

        self.scale = 1.0
        self.templates = {}
        self.set_scale(1.0)

        self.monitor = {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}
        self.screen = mss()

        self.frame = None

    def set_scale(self, scale):
        if scale is None:
            scale = 1.0
        self.scale = scale
        self.templates = {}
        for k, v in self.static_templates.items():
            original = cv2.imread(v, 0)
            if original is not None:
                if scale == 1.0:
                    self.templates[k] = original
                else:
                    self.templates[k] = cv2.resize(original, (0,0), fx=scale, fy=scale)

    def detect_scale(self, image=None):
        """
        Scans key templates across scales to determine the current game scaling factor.
        """
        if image is None:
            if self.frame is None:
                self.refresh_frame()
            image = self.frame

        best_scale = 1.0
        best_val = 0.0
        
        candidates = ['bison-health-bar', 'next-button', 'tap-to-continue', 'cancel-button']
        scales = np.linspace(0.5, 1.8, 66)
        
        for name in candidates:
            original_path = self.static_templates[name]
            template = cv2.imread(original_path, 0)
            if template is None:
                continue
                
            for scale in scales:
                scaled_template = cv2.resize(template, (0,0), fx=scale, fy=scale)
                if scaled_template.shape[1] > image.shape[1] or scaled_template.shape[0] > image.shape[0]:
                    continue
                res = cv2.matchTemplate(image, scaled_template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                if max_val > best_val:
                    best_val = max_val
                    best_scale = scale
            if best_val > 0.8:
                break
                
        if best_val > 0.8:
            return best_scale
        return None

    def take_screenshot(self):
        sct_img = self.screen.grab(self.monitor)
        img = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
        img = np.array(img)
        img = self.convert_rgb_to_bgr(img)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        return img_gray

    def get_image(self, path):
        return cv2.imread(path, 0)

    def bgr_to_rgb(self, img):
        b,g,r = cv2.split(img)
        return cv2.merge([r,g,b])

    def convert_rgb_to_bgr(self, img):
        return img[:, :, ::-1]

    def match_template(self, img_grayscale, template, threshold=0.9):
        """
        Matches template image in a target grayscaled image
        """

        res = cv2.matchTemplate(img_grayscale, template, cv2.TM_CCOEFF_NORMED)
        matches = np.where(res >= threshold)
        return matches

    def find_template(self, name, image=None, threshold=0.9):
        if image is None:
            if self.frame is None:
                self.refresh_frame()

            image = self.frame

        return self.match_template(
            image,
            self.templates[name],
            threshold
        )

    def scaled_find_template(self, name, image=None, threshold=0.9, scales=[1.0, 0.9, 1.1]):
        if image is None:
            if self.frame is None:
                self.refresh_frame()

            image = self.frame

        initial_template = self.templates[name]
        for scale in scales:
            scaled_template = cv2.resize(initial_template, (0,0), fx=scale, fy=scale)
            matches = self.match_template(
                image,
                scaled_template,
                threshold
            )
            if np.shape(matches)[1] >= 1:
                return matches
        return matches

    def refresh_frame(self):
        self.frame = self.take_screenshot()
