import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QVBoxLayout, QLabel, QGroupBox, QSizePolicy)

class ImageTile(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        self.setStyleSheet("""
            QGroupBox {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 6px;
                margin-top: 14px;
                font-weight: bold;
                color: #d0d0d0;
                subcontrol-position: top left;
                subcontrol-origin: margin;
                padding: 16px 6px 6px 6px;
            }
            QGroupBox::title {
                subcontrol-position: top left;
                subcontrol-origin: margin;
                left: 10px;
                top: 2px;
                color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        
        self.image_label = QLabel("Brak danych")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            background-color: #111111; 
            color: #666666; 
            border-radius: 4px;
            border: 1px solid #222222;
        """)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(320, 240)
        
        layout.addWidget(self.image_label)

    def update_image(self, cv_img):
        if cv_img is None:
            return
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(pix)