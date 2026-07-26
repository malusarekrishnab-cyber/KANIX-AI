import sys
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, 
    QLabel, QLineEdit, QPushButton, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen

class LoginScreen(QDialog):
    def __init__(self, auth_manager):
        super().__init__()
        self.auth_manager = auth_manager
        self.scan_line_y = 0
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("KANIX AI - Login")
        self.setFixedSize(400, 550)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #050a15;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 50, 30, 40)
        layout.setSpacing(25)
        
        # Logo / Title
        self.title = QLabel("KANIX AI")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color: #00f0ff; font-size: 36px; font-weight: bold; letter-spacing: 2px;")
        
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(20)
        glow.setColor(QColor(0, 240, 255))
        glow.setOffset(0, 0)
        self.title.setGraphicsEffect(glow)
        layout.addWidget(self.title)
        
        layout.addSpacing(20)
        
        # Username
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("USERNAME")
        self.username_input.setText("admin")
        self.username_input.setStyleSheet(self._input_style())
        layout.addWidget(self.username_input)
        
        # Password
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("PASSWORD")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet(self._input_style())
        layout.addWidget(self.password_input)
        
        # Error Label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ff3366; font-weight: bold;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.error_label)
        
        # Login Button
        self.login_btn = QPushButton("AUTHENTICATE")
        self.login_btn.setStyleSheet(self._btn_style())
        self.login_btn.clicked.connect(self.handle_login)
        
        btn_glow = QGraphicsDropShadowEffect()
        btn_glow.setBlurRadius(15)
        btn_glow.setColor(QColor(0, 240, 255))
        btn_glow.setOffset(0, 0)
        self.login_btn.setGraphicsEffect(btn_glow)
        layout.addWidget(self.login_btn)
        
        # Exit button
        self.exit_btn = QPushButton("ABORT")
        self.exit_btn.setStyleSheet("color: #666; background: transparent; border: none; font-weight: bold;")
        self.exit_btn.clicked.connect(self.reject)
        layout.addWidget(self.exit_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Scanner line animation
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_scan_line)
        self.anim_timer.start(30)
        
    def _input_style(self):
        return """
            QLineEdit {
                background-color: rgba(0, 240, 255, 0.05);
                border: 1px solid rgba(0, 240, 255, 0.3);
                border-radius: 5px;
                color: #fff;
                padding: 15px;
                font-size: 14px;
                font-weight: bold;
            }
            QLineEdit:focus { border: 1px solid #00f0ff; }
        """
        
    def _btn_style(self):
        return """
            QPushButton {
                background-color: rgba(0, 240, 255, 0.1);
                color: #00f0ff;
                border: 1px solid #00f0ff;
                border-radius: 5px;
                padding: 15px;
                font-size: 16px;
                font-weight: bold;
                letter-spacing: 2px;
            }
            QPushButton:hover { background-color: rgba(0, 240, 255, 0.3); }
        """

    def handle_login(self):
        user = self.username_input.text().strip()
        pwd = self.password_input.text().strip()
        
        if self.auth_manager.login_password(user, pwd):
            self.accept()
        else:
            if self.auth_manager.is_locked_out():
                self.error_label.setText("LOCKED OUT. WAIT 5 MIN.")
            else:
                self.error_label.setText("ACCESS DENIED")

    def update_scan_line(self):
        self.scan_line_y += 2
        if self.scan_line_y > self.height():
            self.scan_line_y = 0
        self.update()
        
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(QColor(0, 240, 255, 50))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(0, self.scan_line_y, self.width(), self.scan_line_y)
