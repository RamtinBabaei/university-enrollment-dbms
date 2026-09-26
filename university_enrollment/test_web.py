"""Smoke tests for the local browser interface and its form workflow."""

import tempfile
import threading
import unittest
import sqlite3
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import db
import web


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "web.db"
        db.initialize(self.path)
        self.server = web.make_server(self.path, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def get(self, path):
        with urlopen(self.url + path) as response:
            return response.read().decode("utf-8")

    def post(self, action, **values):
        data = urlencode({"csrf": self.server.csrf, **values}).encode("utf-8")
        with urlopen(Request(self.url + "/" + action, data=data, method="POST")) as response:
            return response.read().decode("utf-8")

    def test_pages_and_forms_work_together(self):
        for page in ("/", "/students", "/courses", "/sections", "/enrollments", "/transcript"):
            self.assertIn("<!doctype html>", self.get(page))
        self.post("add-student", number="S7", name="Sara", email="sara@example.com")
        self.post("add-course", code="CS300", title="HCI", credits="3")
        self.post("add-section", course_code="CS300", term="2026-Fall",
                  section_number="1", instructor="Dr. A", capacity="2")
        section = db.list_sections(self.path)[0]["id"]
        self.post("enroll", student_number="S7", section_id=str(section))
        self.post("grade", student_number="S7", section_id=str(section), score="87")
        self.assertIn("87.0", self.get("/transcript?student=S7"))
        self.assertIn("1 / 2", self.get("/sections"))
        self.post("drop", student_number="S7", section_id=str(section))
        self.assertEqual(db.list_sections(self.path)[0]["seats_left"], 2)

    def test_rejected_bad_data_and_html_escaping(self):
        self.post("add-student", number="S8", name="<script>alert(1)</script>", email="s8@example.com")
        page = self.get("/students")
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)
        bad = self.post("add-student", number="S8", name="Again", email="another@example.com")
        self.assertIn("عملیات انجام نشد", bad)
        self.assertEqual(len(db.list_students(self.path)), 1)

    def test_broken_database_shows_error_page(self):
        invalid = Path(self.temp.name) / "wrong_schema.db"
        sqlite3.connect(invalid).close()
        self.server.db_path = invalid
        with self.assertRaises(HTTPError) as result:
            self.get("/students")
        self.assertEqual(result.exception.code, 500)
        self.assertIn("صفحه بارگذاری نشد", result.exception.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
