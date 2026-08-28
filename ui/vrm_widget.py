import os
import sys
import http.server
import socketserver
import threading
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()

class LocalAssetServer:
    _server = None
    _port = 8888

    @classmethod
    def start(cls) -> int:
        if cls._server is not None:
            return cls._port

        # Change working directory to project root for serving assets
        os.chdir(str(BASE_DIR))
        handler = http.server.SimpleHTTPRequestHandler
        for port in range(8888, 8999):
            try:
                cls._server = socketserver.TCPServer(("127.0.0.1", port), handler)
                cls._port = port
                t = threading.Thread(target=cls._server.serve_forever, daemon=True)
                t.start()
                print(f"[AssetServer] Serving assets at http://127.0.0.1:{port}/")
                return port
            except OSError:
                continue
        return 8888

class VRMAvatarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        port = LocalAssetServer.start()
        self.url = QUrl(f"http://127.0.0.1:{port}/assets/vrm_viewer.html")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView(self)
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        layout.addWidget(self.web_view)
        self.web_view.load(self.url)

    def set_expression(self, emotion: str):
        js = f"if (window.setExpression) window.setExpression('{emotion}');"
        self.web_view.page().runJavaScript(js)

    def play_animation(self, anim_name: str):
        js = f"if (window.playAnimation) window.playAnimation('{anim_name}');"
        self.web_view.page().runJavaScript(js)

    def set_speaking(self, is_speaking: bool):
        val = "true" if is_speaking else "false"
        js = f"if (window.setLipSync) window.setLipSync({val});"
        self.web_view.page().runJavaScript(js)

    def set_live_mode(self, enabled: bool):
        val = "true" if enabled else "false"
        js = f"if (window.setLiveMode) window.setLiveMode({val});"
        self.web_view.page().runJavaScript(js)
