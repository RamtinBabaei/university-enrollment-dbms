"""Run with `python -m unittest -v` from the project directory."""

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import db


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.db"
        db.initialize(self.path)
        db.add_student(self.path, "S1", "Alice", "alice@example.com")
        db.add_student(self.path, "S2", "Bob", "bob@example.com")
        db.add_course(self.path, "DB101", "Databases", 3)
        self.section = db.add_section(self.path, "DB101", "2026-Fall", 1, "Dr. Lee", 1)

    def tearDown(self):
        self.temp.cleanup()

    def test_capacity_drop_and_reenrollment(self):
        db.enroll(self.path, "S1", self.section)
        with self.assertRaisesRegex(db.DomainError, "full"):
            db.enroll(self.path, "S2", self.section)
        db.drop(self.path, "S1", self.section)
        db.enroll(self.path, "S2", self.section)
        self.assertEqual(db.list_sections(self.path)[0]["seats_left"], 0)
        db.drop(self.path, "S2", self.section)
        db.enroll(self.path, "S2", self.section)
        with db.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM enrollments").fetchone()[0], 2)

    def test_duplicate_section_and_same_course_term(self):
        second = db.add_section(self.path, "DB101", "2026-Fall", 2, "Dr. Kay", 5)
        db.enroll(self.path, "S1", self.section)
        with self.assertRaisesRegex(db.DomainError, "already enrolled"):
            db.enroll(self.path, "S1", self.section)
        with self.assertRaisesRegex(db.DomainError, "already takes"):
            db.enroll(self.path, "S1", second)
        self.assertEqual(db.list_sections(self.path)[1]["enrolled"], 0)

    def test_grades_and_weighted_average(self):
        db.add_course(self.path, "M101", "Mathematics", 2)
        second = db.add_section(self.path, "M101", "2026-Fall", 1, "Dr. Kay", 3)
        db.enroll(self.path, "S1", self.section)
        db.enroll(self.path, "S1", second)
        db.set_grade(self.path, "S1", self.section, 90)
        db.set_grade(self.path, "S1", second, 75)
        report = db.transcript(self.path, "S1")
        self.assertEqual(report["weighted_average_100"], 84)
        self.assertEqual(report["graded_credits"], 5)
        with self.assertRaisesRegex(db.DomainError, "between"):
            db.set_grade(self.path, "S1", second, 101)
        db.drop(self.path, "S1", second)
        self.assertEqual(db.transcript(self.path, "S1")["weighted_average_100"], 90)

    def test_constraints_and_crud(self):
        with self.assertRaises(sqlite3.IntegrityError):
            db.add_student(self.path, "S1", "Duplicate", "unique@example.com")
        with self.assertRaises(sqlite3.IntegrityError):
            db.add_course(self.path, "INVALID", "Bad credits", 0)
        db.update_student(self.path, "S2", "Bobby", "bobby@example.com")
        self.assertEqual(db.list_students(self.path)[1]["full_name"], "Bobby")
        db.update_course(self.path, "DB101", "SQL Databases", 4)
        self.assertEqual(db.list_courses(self.path)[0]["credits"], 4)
        db.delete_student(self.path, "S2")
        with self.assertRaises(sqlite3.IntegrityError):
            db.delete_course(self.path, "DB101")  # Has a section.

    def test_parallel_requests_never_overfill(self):
        def attempt(number):
            try:
                db.enroll(self.path, number, self.section)
                return True
            except db.DomainError as exc:
                self.assertIn("full", str(exc))
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, ("S1", "S2")))
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual(db.list_sections(self.path)[0]["enrolled"], 1)


if __name__ == "__main__":
    unittest.main()
