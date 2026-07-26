import os
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QColor, QTransform

class AnimatedAvatar(QWidget):
    def __init__(self, parent=None, base_image_path=None):
        super().__init__(parent)
        self.setFixedSize(300, 350)
        self.base_image_path = base_image_path
        
        self.current_emotion = "neutral"
        self.is_speaking = False
        self.lip_state = False
        
        self.emotions = {
            "neutral": QColor("#3498db"),
            "happy": QColor("#2ecc71"),
            "sad": QColor("#95a5a6"),
            "angry": QColor("#e74c3c"),
            "thinking": QColor("#f39c12"),
            "speaking": QColor("#9b59b6")
        }
        
        self.initUI()
        self.setupAnimations()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(300, 300)
        
        self.glow_effect = QGraphicsDropShadowEffect(self)
        self.glow_effect.setBlurRadius(20)
        self.glow_effect.setOffset(0, 0)
        self.glow_effect.setColor(self.emotions["neutral"])
        self.image_label.setGraphicsEffect(self.glow_effect)
        
        self.status_label = QLabel("NEUTRAL", self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        
        layout.addWidget(self.image_label)
        layout.addWidget(self.status_label)
        
        self.load_base_pixmap()
        self.update_view()
        
    def load_base_pixmap(self):
        if self.base_image_path and os.path.exists(self.base_image_path):
            self.base_pixmap = QPixmap(self.base_image_path)
        else:
            # Fallback empty pixmap
            self.base_pixmap = QPixmap(280, 280)
            self.base_pixmap.fill(Qt.GlobalColor.transparent)
            
    def setupAnimations(self):
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.on_timer)
        self.anim_timer.start(100) # 100ms intervals
        
    def on_timer(self):
        if self.is_speaking:
            self.lip_state = not self.lip_state
            self.update_view()

    def update_view(self):
        if self.base_pixmap.isNull():
            self.image_label.setText(f"[AVATAR]")
            return
            
        scale_factor = 1.0
        if self.is_speaking:
            scale_factor = 1.0 if self.lip_state else 0.85
            
        scaled_size = int(280 * scale_factor)
        pixmap = self.base_pixmap.scaled(
            scaled_size, scaled_size, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(pixmap)
        
        color = self.emotions.get(self.current_emotion, self.emotions["neutral"])
        if self.is_speaking:
            color = self.emotions["speaking"]
            
        self.glow_effect.setColor(color)
        self.status_label.setText(self.current_emotion.upper() if not self.is_speaking else "SPEAKING")
        self.status_label.setStyleSheet(f"color: {color.name()}; font-weight: bold; font-size: 14px;")

    def set_emotion(self, emotion: str):
        self.current_emotion = emotion
        self.update_view()
        
    def set_speaking(self, is_speaking: bool):
        self.is_speaking = is_speaking
        if not is_speaking:
            self.lip_state = False
        self.update_view()
