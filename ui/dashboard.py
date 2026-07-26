import psutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QTextEdit, QLineEdit, QPushButton, QSplitter
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from ui.animated_girl import AnimatedAvatar

class Dashboard(QWidget):
    def __init__(self, parent=None, base_image_path=None):
        super().__init__(parent)
        self.setWindowTitle("KANIX AI Dashboard")
        self.resize(1000, 600)
        self.setStyleSheet("background-color: #0a0e17; color: white;")
        self.base_image_path = base_image_path
        
        self.is_muted = False
        self.voice_input_enabled = True
        self.current_mode = "QWEN" # Blue mode default
        
        # Callback for text input
        self.on_text_command = None
        
        self.initUI()
        
        # System stats timer
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_system_stats)
        self.stats_timer.start(2000)
        
    def initUI(self):
        main_layout = QVBoxLayout(self)
        
        # Splitter for Left/Right panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Panel (Avatar + Controls)
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        
        self.avatar = AnimatedAvatar(base_image_path=self.base_image_path)
        left_layout.addWidget(self.avatar, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Controls
        controls_layout = QHBoxLayout()
        self.mute_btn = QPushButton("MUTE")
        self.mute_btn.setStyleSheet(self._btn_style())
        self.mute_btn.clicked.connect(self.toggle_mute)
        
        self.voice_btn = QPushButton("VOICE: ON")
        self.voice_btn.setStyleSheet(self._btn_style())
        self.voice_btn.clicked.connect(self.toggle_voice)
        
        controls_layout.addWidget(self.mute_btn)
        controls_layout.addWidget(self.voice_btn)
        left_layout.addLayout(controls_layout)
        
        # Status Label
        self.mode_label = QLabel("MODE: BLUE (SIMPLE)")
        self.mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mode_label.setStyleSheet("font-weight: bold; color: #3498db; margin-top: 10px;")
        left_layout.addWidget(self.mode_label)
        
        self.online_label = QLabel("STATUS: ONLINE")
        self.online_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.online_label.setStyleSheet("font-weight: bold; color: #2ecc71;")
        left_layout.addWidget(self.online_label)
        
        left_layout.addStretch()
        
        # Right Panel (Chat + Input)
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background-color: #111827; border: 1px solid #374151; padding: 10px; font-size: 14px;")
        right_layout.addWidget(self.chat_display)
        
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your command here...")
        self.input_field.setStyleSheet("background-color: #1f2937; border: 1px solid #4b5563; padding: 10px; border-radius: 5px;")
        self.input_field.returnPressed.connect(self.send_command)
        
        self.send_btn = QPushButton("SEND")
        self.send_btn.setStyleSheet(self._btn_style())
        self.send_btn.clicked.connect(self.send_command)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        right_layout.addLayout(input_layout)
        
        # Add to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 650])
        main_layout.addWidget(splitter)
        
        # Status Bar
        self.status_bar = QLabel("CPU: 0% | MEMORY: 0% | RESPONSE: --")
        self.status_bar.setStyleSheet("background-color: #111827; padding: 5px; border-top: 1px solid #374151;")
        main_layout.addWidget(self.status_bar)
        
    def _btn_style(self):
        return """
            QPushButton {
                background-color: #374151;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #4b5563; }
        """
        
    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.mute_btn.setText("UNMUTE" if self.is_muted else "MUTE")
        
    def toggle_voice(self):
        self.voice_input_enabled = not self.voice_input_enabled
        self.voice_btn.setText("VOICE: ON" if self.voice_input_enabled else "VOICE: OFF")
        
    def send_command(self):
        text = self.input_field.text().strip()
        if text and self.on_text_command:
            self.input_field.clear()
            self.on_text_command(text)
            
    def add_message(self, text: str, is_user: bool = False):
        color = "#3498db" if is_user else "#2ecc71" # Blue for user, Green for KANIX
        
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(f"\n{text}\n", fmt)
        self.chat_display.setTextCursor(cursor)
        
    def set_mode(self, mode: str):
        self.current_mode = mode
        if mode == "DEEPSEEK":
            self.setStyleSheet("background-color: #1a0f0f; color: white;") # Dark red
            self.mode_label.setText("MODE: RED (CODING)")
            self.mode_label.setStyleSheet("font-weight: bold; color: #e74c3c; margin-top: 10px;")
        else:
            self.setStyleSheet("background-color: #0a0e17; color: white;") # Dark blue
            self.mode_label.setText("MODE: BLUE (SIMPLE)")
            self.mode_label.setStyleSheet("font-weight: bold; color: #3498db; margin-top: 10px;")
            
    def set_status(self, text: str):
        # Used by KANIX to show THINKING, LISTENING, etc.
        pass

    def update_system_stats(self):
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        resp = getattr(self, "last_response_time", "--")
        self.status_bar.setText(f"CPU: {cpu}% | MEMORY: {mem}% | RESPONSE: {resp}")
        
    def update_stats(self, response_time: str):
        self.last_response_time = response_time
        self.update_system_stats()
