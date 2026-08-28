import sys
import os
import time
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

class TestKanixE2E(unittest.TestCase):

    def test_01_compilation(self):
        import py_compile, glob
        fails = []
        for f in glob.glob(str(BASE_DIR / "**/*.py"), recursive=True):
            try:
                py_compile.compile(f, doraise=True)
            except Exception as e:
                fails.append((f, str(e)))
        self.assertEqual(len(fails), 0, f"Compilation failures: {fails}")

    def test_02_vrm_assets(self):
        vrm_model = BASE_DIR / "assets" / "models" / "kanix_avatar.vrm"
        vrm_html = BASE_DIR / "assets" / "vrm_viewer.html"
        self.assertTrue(vrm_model.exists(), "kanix_avatar.vrm missing")
        self.assertTrue(vrm_html.exists(), "vrm_viewer.html missing")
        self.assertGreater(vrm_model.stat().st_size, 100, "kanix_avatar.vrm is empty")
        self.assertGreater(vrm_html.stat().st_size, 100, "vrm_viewer.html is empty")

    def test_03_screen_vision_lazy_load(self):
        os.environ["SCREEN_VISION_ENABLED"] = "false"
        import actions.screen_processor as sp
        res = sp.screen_process({})
        self.assertIn("disabled", res.lower())

    def test_04_job_agent_safety(self):
        import actions.job_agent as ja
        profile = {"skills": ["Python"], "experience_years": 1, "location": "Remote"}

        # Test low match score blocked
        res_apply = ja.job_agent_action({"action": "apply", "query": "Senior Architect"}, profile)
        self.assertTrue("below required minimum" in res_apply or "ineligible" in res_apply.lower())

    def test_05_router(self):
        from core.router import router
        state = router.get(force=True)
        self.assertIsNotNone(state)
        self.assertIn(state.main_ai, ["gemini", "ollama"])

    def test_06_single_instance(self):
        from core.system_features import ensure_single_instance
        res = ensure_single_instance(port=49999)
        self.assertTrue(res, "Single instance lock failed")

    def test_07_agents_imports(self):
        import agent.planner as planner
        import agent.executor as executor
        import agent.error_handler as error_handler
        import agent.task_queue as task_queue

        self.assertIsNotNone(planner.create_plan)
        self.assertIsNotNone(executor.AgentExecutor)
        self.assertIsNotNone(error_handler.analyze_error)
        self.assertIsNotNone(task_queue.get_queue)

    def test_08_ui_and_vrm_widget(self):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        from ui import kanixUI

        app = QApplication.instance() or QApplication(sys.argv)
        ui = kanixUI("face.png")
        self.assertIsNotNone(ui._win)
        self.assertIsNotNone(ui._win.vrm_avatar)

        # Test live mode toggle
        ui._win.toggle_live_mode()
        self.assertTrue(ui._win._is_live_mode)
        ui._win.exit_live_mode()
        self.assertFalse(ui._win._is_live_mode)

if __name__ == "__main__":
    unittest.main()
