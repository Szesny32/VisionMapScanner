import cv2
import numpy as np
from PySide6.QtWidgets import QLabel, QSlider
from PySide6.QtCore import Qt
from layer.base_layer import BaseLayer

class KeypointLayer(BaseLayer):
    def __init__(self):
        super().__init__("Keypoint Matching")
        self.outputs = ["matches_visual"]
        self.provides = {"matches_visual": "matches_visual"}
        self.nfeatures = 500
        self.max_draw_matches = 50
        self.orb = cv2.ORB_create(nfeatures=self.nfeatures)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    def _build_custom_controls(self, layout):
        # Suwak: Liczba cech ORB
        lbl_feat = QLabel(f"ORB Features: {self.nfeatures}")
        slider_feat = QSlider(Qt.Horizontal)
        slider_feat.setRange(100, 2000)
        slider_feat.setValue(self.nfeatures)

        def on_feat_change(val):
            self.nfeatures = val
            lbl_feat.setText(f"ORB Features: {val}")
            self.orb = cv2.ORB_create(nfeatures=self.nfeatures)
            self._cache.clear()

        slider_feat.valueChanged.connect(on_feat_change)

        # Suwak: Liczba rysowanych dopasowań
        lbl_match = QLabel(f"Max Matches Draw: {self.max_draw_matches}")
        slider_match = QSlider(Qt.Horizontal)
        slider_match.setRange(10, 200)
        slider_match.setValue(self.max_draw_matches)

        def on_match_change(val):
            self.max_draw_matches = val
            lbl_match.setText(f"Max Matches Draw: {val}")

        slider_match.valueChanged.connect(on_match_change)

        layout.addWidget(lbl_feat)
        layout.addWidget(slider_feat)
        layout.addWidget(lbl_match)
        layout.addWidget(slider_match)

    def process(self, data):
        frame_id = data.get('frame_id', None)
        
        if self._check_cache(frame_id, 'matches_visual'):
            return

        left = data.get('left')
        right = data.get('right')
        
        if left is None or right is None:
            self.context['matches_visual'] = None
            return

        gray_left = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        gray_right = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)

        kp1, des1 = self.orb.detectAndCompute(gray_left, None)
        kp2, des2 = self.orb.detectAndCompute(gray_right, None)

        if des1 is not None and des2 is not None and len(des1) > 0 and len(des2) > 0:
            matches = self.matcher.match(des1, des2)
            matches = sorted(matches, key=lambda x: x.distance)
            
            match_img = cv2.drawMatches(
                left, kp1, right, kp2, matches[:self.max_draw_matches], None, 
                flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS
            )
            self.context['matches_visual'] = match_img
        else:
            self.context['matches_visual'] = np.hstack((left, right))

        self._save_to_cache(frame_id, 'matches_visual', self.context['matches_visual'])

    def draw(self, data):
        return self.context.get('matches_visual', None)