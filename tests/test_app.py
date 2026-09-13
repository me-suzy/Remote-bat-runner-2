import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        source = Path(__file__).resolve().parents[1]
        shutil.copy2(source / "app.py", root / "app.py")
        shutil.copytree(source / "templates", root / "templates")
        (root / "secret.txt").write_text("test-private-key")
        config = types.ModuleType("config")
        for key, value in dict(BAT_PATH=str(root / "job.bat"), SCAN_ROOT=str(root / "pdfs"), APP_TITLE="Test", SCAN_FILE_LIMIT=2, SCAN_FOLDER_LIMIT=2, SCAN_FILE_EXTS=(".pdf",), DAILY_PDF_COUNT_ROOTS=[str(root / "pdfs" / "Temporare")]).items():
            setattr(config, key, value)
        cls.old_config = sys.modules.get("config")
        sys.modules["config"] = config
        spec = importlib.util.spec_from_file_location("tested_runner", root / "app.py")
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        cls.mod.app.config.update(TESTING=True)
        cls.mod.SCAN_ROOT.mkdir()

    @classmethod
    def tearDownClass(cls):
        if cls.old_config is None: sys.modules.pop("config", None)
        else: sys.modules["config"] = cls.old_config
        cls.tmp.cleanup()

    def test_auth_and_no_secret_in_html(self):
        c = self.mod.app.test_client()
        for route in ("/", "/files", "/chatgpt", "/remote", "/remote/windows"):
            self.assertEqual(c.get(route).status_code, 403)
        for route in ('/remote/frame','/remote/activate','/remote/action'):
            self.assertEqual(c.post(route,json={}).status_code,403)
        self.assertEqual(c.post("/open-chatgpt").status_code, 403)
        r = c.get("/chatgpt?k=test-private-key", base_url="https://localhost")
        self.assertEqual(r.status_code, 302)
        self.assertIn("HttpOnly", r.headers["Set-Cookie"])
        for route in ("/", "/files", "/chatgpt"):
            r = c.get(route, base_url="https://localhost")
            self.assertEqual(r.status_code, 200)
            self.assertNotIn(b"test-private-key", r.data)
            self.assertEqual(r.headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(c.post("/open-chatgpt", base_url="https://localhost").status_code, 403)
        self.assertEqual(c.get("/?k=wrong", base_url="https://localhost").status_code, 403)

    def test_launch_success_failure_and_timeout(self):
        c = self.mod.app.test_client()
        script = Path(self.tmp.name) / "open.ps1"
        script.touch()
        with patch.object(self.mod, "CHATGPT_SCRIPT", script):
            for result, expected in [(subprocess.CompletedProcess([],0,"Activated", ""),200),(subprocess.CompletedProcess([],1,"", "Failed"),500)]:
                with patch.object(self.mod.subprocess,"run",return_value=result):
                    self.assertEqual(c.post("/open-chatgpt",headers={"X-Key":"test-private-key"}).status_code,expected)
            with patch.object(self.mod.subprocess,"run",side_effect=subprocess.TimeoutExpired("powershell",20)):
                self.assertEqual(c.post("/open-chatgpt",headers={"X-Key":"test-private-key"}).status_code,500)

    def test_completed_log_sessions_and_duplicates(self):
        from datetime import datetime
        start,end,_,_=self.mod._daily_pdf_window()
        date=datetime.fromtimestamp(start).strftime("%m/%d/%Y")
        log=Path(self.tmp.name)/"batch.log"
        log.write_text(f"Data: Sat {date} 5:00:00\n Confirmat pe disk: source.pdf (40 bytes)\n Confirmat pe disk: source.pdf (40 bytes)\nData: Sat {date} 7:10:00\nData: Sat {date} 7:50:00\n Confirmat pe disk: outside.pdf (40 bytes)\nData: Sat {date} 8:10:00\n",encoding="utf-8")
        with patch.object(self.mod.config,"DAILY_PDF_LOG_GLOBS",[str(log)],create=True):
            self.assertEqual(self.mod._confirmed_download_names(start,end),{"source.pdf"})

    def test_window_moves_copies_and_merged_exclusion(self):
        root=self.mod.SCAN_ROOT
        dest=root/"Temporare"/"Issue"
        dest.mkdir(parents=True)
        start,end,_,_=self.mod._daily_pdf_window()
        def pdf(name,stamp,data=b"sample"):
            file=root/name
            file.write_bytes(data)
            os.utime(file,(stamp,stamp))
            return file
        a=pdf("issue__pages1-50.pdf",start)
        shutil.copy2(a,dest/a.name)
        b=pdf("issue__pages51-100.pdf",end-1)
        shutil.move(str(b),str(dest/b.name))
        pdf("old__pages1-50.pdf",start-1)
        pdf("late__pages1-50.pdf",end)
        pdf("merged.pdf",start+50)
        with patch.object(self.mod.config,"DAILY_PDF_NAME_PATTERN",r"__pages\d+-\d+\.pdf$",create=True):
            self.assertEqual(self.mod._daily_pdf_count(),2)
        self.assertEqual(len(self.mod._latest_pdfs(root,2,(".pdf",))),2)

if __name__ == "__main__": unittest.main()
