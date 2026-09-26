"""Database operations for the university enrollment project."""

from __future__ import annotations

import sqlite3
import math
from contextlib import contextmanager
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")


class DomainError(ValueError):
    """A request violates a business rule or refers to a missing record."""


@contextmanager
def connect(path: str | Path):
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


def initialize(path: str | Path) -> None:
    with connect(path) as db:
        db.executescript(SCHEMA.read_text(encoding="utf-8"))
        db.commit()


def add_student(path: str | Path, number: str, name: str, email: str) -> int:
    number, name, email = number.strip(), name.strip(), email.strip().lower()
    if not number or not name or not email:
        raise DomainError("Student number, name and email are required")
    with connect(path) as db, db:
        return db.execute(
            "INSERT INTO students(student_number, full_name, email) VALUES (?, ?, ?)",
            (number, name, email),
        ).lastrowid


def update_student(path: str | Path, number: str, name: str, email: str) -> None:
    name, email = name.strip(), email.strip().lower()
    if not name or not email:
        raise DomainError("Name and email are required")
    with connect(path) as db, db:
        cursor = db.execute(
            "UPDATE students SET full_name = ?, email = ? WHERE student_number = ?",
            (name, email, number.strip()),
        )
        if cursor.rowcount == 0:
            raise DomainError("Student not found")


def delete_student(path: str | Path, number: str) -> None:
    with connect(path) as db, db:
        cursor = db.execute("DELETE FROM students WHERE student_number = ?", (number.strip(),))
        if cursor.rowcount == 0:
            raise DomainError("Student not found")


def add_course(path: str | Path, code: str, title: str, credits: int) -> int:
    code, title = code.strip().upper(), title.strip()
    if not code or not title:
        raise DomainError("Course code and title are required")
    with connect(path) as db, db:
        return db.execute(
            "INSERT INTO courses(code, title, credits) VALUES (?, ?, ?)",
            (code, title, credits),
        ).lastrowid


def update_course(path: str | Path, code: str, title: str, credits: int) -> None:
    title = title.strip()
    if not title:
        raise DomainError("Title is required")
    with connect(path) as db, db:
        cursor = db.execute(
            "UPDATE courses SET title = ?, credits = ? WHERE code = ?",
            (title, credits, code.strip().upper()),
        )
        if cursor.rowcount == 0:
            raise DomainError("Course not found")


def delete_course(path: str | Path, code: str) -> None:
    with connect(path) as db, db:
        cursor = db.execute("DELETE FROM courses WHERE code = ?", (code.strip().upper(),))
        if cursor.rowcount == 0:
            raise DomainError("Course not found")


def add_section(
    path: str | Path, course_code: str, term: str, section_number: int,
    instructor: str, capacity: int,
) -> int:
    term, instructor = term.strip(), instructor.strip()
    if not term or not instructor:
        raise DomainError("Term and instructor are required")
    with connect(path) as db, db:
        course = db.execute("SELECT id FROM courses WHERE code = ?", (course_code.strip().upper(),)).fetchone()
        if course is None:
            raise DomainError("Course not found")
        return db.execute(
            "INSERT INTO sections(course_id, term, section_number, instructor, capacity) "
            "VALUES (?, ?, ?, ?, ?)",
            (course["id"], term, section_number, instructor, capacity),
        ).lastrowid


def enroll(path: str | Path, student_number: str, section_id: int) -> None:
    # BEGIN IMMEDIATE serializes the capacity check and write across processes.
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            student = db.execute(
                "SELECT id FROM students WHERE student_number = ?", (student_number.strip(),)
            ).fetchone()
            if student is None:
                raise DomainError("Student not found")
            section = db.execute(
                "SELECT s.capacity, s.course_id, s.term FROM sections s WHERE s.id = ?", (section_id,)
            ).fetchone()
            if section is None:
                raise DomainError("Section not found")
            existing = db.execute(
                "SELECT status FROM enrollments WHERE student_id = ? AND section_id = ?",
                (student["id"], section_id),
            ).fetchone()
            if existing and existing["status"] == "enrolled":
                raise DomainError("Student is already enrolled in this section")
            other_section = db.execute(
                "SELECT 1 FROM enrollments e JOIN sections s ON s.id = e.section_id "
                "WHERE e.student_id = ? AND e.status = 'enrolled' "
                "AND s.course_id = ? AND s.term = ?",
                (student["id"], section["course_id"], section["term"]),
            ).fetchone()
            if other_section:
                raise DomainError("Student already takes this course in this term")
            occupied = db.execute(
                "SELECT COUNT(*) FROM enrollments WHERE section_id = ? AND status = 'enrolled'",
                (section_id,),
            ).fetchone()[0]
            if occupied >= section["capacity"]:
                raise DomainError("Section is full")
            if existing:
                db.execute(
                    "UPDATE enrollments SET status = 'enrolled', grade = NULL, "
                    "enrolled_at = CURRENT_TIMESTAMP WHERE student_id = ? AND section_id = ?",
                    (student["id"], section_id),
                )
            else:
                db.execute(
                    "INSERT INTO enrollments(student_id, section_id) VALUES (?, ?)",
                    (student["id"], section_id),
                )
            db.commit()
        except Exception:
            db.rollback()
            raise


def drop(path: str | Path, student_number: str, section_id: int) -> None:
    with connect(path) as db, db:
        cursor = db.execute(
            "UPDATE enrollments SET status = 'dropped', grade = NULL "
            "WHERE student_id = (SELECT id FROM students WHERE student_number = ?) "
            "AND section_id = ? AND status = 'enrolled'",
            (student_number.strip(), section_id),
        )
        if cursor.rowcount == 0:
            raise DomainError("Active enrollment not found")


def set_grade(path: str | Path, student_number: str, section_id: int, grade: float) -> None:
    if not math.isfinite(grade) or not 0 <= grade <= 100:
        raise DomainError("Grade must be between 0 and 100")
    with connect(path) as db, db:
        cursor = db.execute(
            "UPDATE enrollments SET grade = ? "
            "WHERE student_id = (SELECT id FROM students WHERE student_number = ?) "
            "AND section_id = ? AND status = 'enrolled'",
            (grade, student_number.strip(), section_id),
        )
        if cursor.rowcount == 0:
            raise DomainError("Active enrollment not found")


def list_students(path: str | Path) -> list[dict]:
    with connect(path) as db:
        return [dict(row) for row in db.execute(
            "SELECT student_number, full_name, email FROM students ORDER BY student_number"
        )]


def list_courses(path: str | Path) -> list[dict]:
    with connect(path) as db:
        return [dict(row) for row in db.execute(
            "SELECT code, title, credits FROM courses ORDER BY code"
        )]


def list_sections(path: str | Path, term: str | None = None) -> list[dict]:
    query = (
        "SELECT s.id, c.code, c.title, s.term, s.section_number, s.instructor, "
        "s.capacity, COUNT(e.id) AS enrolled, s.capacity - COUNT(e.id) AS seats_left "
        "FROM sections s JOIN courses c ON c.id = s.course_id "
        "LEFT JOIN enrollments e ON e.section_id = s.id AND e.status = 'enrolled' "
        "WHERE (? IS NULL OR s.term = ?) GROUP BY s.id "
        "ORDER BY s.term, c.code, s.section_number"
    )
    with connect(path) as db:
        return [dict(row) for row in db.execute(query, (term, term))]


def list_enrollments(path: str | Path) -> list[dict]:
    with connect(path) as db:
        return [dict(row) for row in db.execute(
            "SELECT st.student_number, st.full_name, s.id AS section_id, "
            "c.code, c.title, s.term, s.section_number, e.grade "
            "FROM enrollments e JOIN students st ON st.id = e.student_id "
            "JOIN sections s ON s.id = e.section_id "
            "JOIN courses c ON c.id = s.course_id "
            "WHERE e.status = 'enrolled' "
            "ORDER BY s.term DESC, c.code, st.student_number"
        )]


def transcript(path: str | Path, student_number: str) -> dict:
    with connect(path) as db:
        student = db.execute(
            "SELECT student_number, full_name FROM students WHERE student_number = ?",
            (student_number.strip(),),
        ).fetchone()
        if student is None:
            raise DomainError("Student not found")
        rows = [dict(row) for row in db.execute(
            "SELECT c.code, c.title, c.credits, s.term, s.section_number, e.grade "
            "FROM enrollments e JOIN sections s ON s.id = e.section_id "
            "JOIN courses c ON c.id = s.course_id "
            "WHERE e.student_id = (SELECT id FROM students WHERE student_number = ?) "
            "AND e.status = 'enrolled' ORDER BY s.term, c.code",
            (student_number.strip(),),
        )]
        graded = [r for r in rows if r["grade"] is not None]
        credits = sum(r["credits"] for r in graded)
        average = round(sum(r["credits"] * r["grade"] for r in graded) / credits, 2) if credits else None
        return {"student": dict(student), "courses": rows, "graded_credits": credits,
                "weighted_average_100": average}
