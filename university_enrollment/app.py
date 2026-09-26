"""Command-line interface. Run `python app.py --help` for commands."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import db


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="University enrollment database")
    p.add_argument("--db", default="university.db", help="SQLite database path (default: university.db)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create tables; safe to run again")

    x = sub.add_parser("add-student")
    x.add_argument("number"); x.add_argument("name"); x.add_argument("email")
    x = sub.add_parser("edit-student")
    x.add_argument("number"); x.add_argument("name"); x.add_argument("email")
    x = sub.add_parser("delete-student")
    x.add_argument("number")
    sub.add_parser("students")

    x = sub.add_parser("add-course")
    x.add_argument("code"); x.add_argument("title"); x.add_argument("credits", type=int)
    x = sub.add_parser("edit-course")
    x.add_argument("code"); x.add_argument("title"); x.add_argument("credits", type=int)
    x = sub.add_parser("delete-course")
    x.add_argument("code")
    sub.add_parser("courses")

    x = sub.add_parser("add-section")
    x.add_argument("course_code"); x.add_argument("term")
    x.add_argument("section_number", type=int); x.add_argument("instructor")
    x.add_argument("capacity", type=int)
    x = sub.add_parser("sections")
    x.add_argument("--term")

    for command in ("enroll", "drop"):
        x = sub.add_parser(command)
        x.add_argument("student_number"); x.add_argument("section_id", type=int)
    x = sub.add_parser("grade")
    x.add_argument("student_number"); x.add_argument("section_id", type=int)
    x.add_argument("score", type=float)
    x = sub.add_parser("transcript")
    x.add_argument("student_number")
    sub.add_parser("seed", help="Load small example dataset into an empty database")
    return p


def seed(path: Path) -> dict:
    db.initialize(path)
    with db.connect(path) as conn:
        if conn.execute("SELECT 1 FROM students LIMIT 1").fetchone() or conn.execute(
            "SELECT 1 FROM courses LIMIT 1"
        ).fetchone() or conn.execute("SELECT 1 FROM sections LIMIT 1").fetchone():
            raise db.DomainError("Seed requires a database with no existing records")
    db.add_student(path, "S1001", "Ava Rahimi", "ava@example.com")
    db.add_student(path, "S1002", "Ramin Moradi", "ramin@example.com")
    db.add_course(path, "CS101", "Introduction to Programming", 3)
    db.add_course(path, "CS202", "Database Systems", 3)
    s1 = db.add_section(path, "CS101", "2026-Fall", 1, "Dr. Farahani", 2)
    s2 = db.add_section(path, "CS202", "2026-Fall", 1, "Dr. Azadi", 1)
    db.enroll(path, "S1001", s1)
    db.enroll(path, "S1001", s2)
    db.enroll(path, "S1002", s1)
    db.set_grade(path, "S1001", s1, 91)
    return {"message": "Example data added", "section_ids": [s1, s2]}


def run(args: argparse.Namespace):
    path = Path(args.db)
    if args.command == "init":
        db.initialize(path)
        return {"message": "Database initialized", "path": str(path)}
    if args.command == "seed":
        return seed(path)
    if not path.is_file():
        raise db.DomainError("Database not found; run the init or seed command first")
    if args.command == "add-student":
        return {"student_id": db.add_student(path, args.number, args.name, args.email)}
    if args.command == "edit-student":
        db.update_student(path, args.number, args.name, args.email)
    elif args.command == "delete-student":
        db.delete_student(path, args.number)
    elif args.command == "students":
        return db.list_students(path)
    elif args.command == "add-course":
        return {"course_id": db.add_course(path, args.code, args.title, args.credits)}
    elif args.command == "edit-course":
        db.update_course(path, args.code, args.title, args.credits)
    elif args.command == "delete-course":
        db.delete_course(path, args.code)
    elif args.command == "courses":
        return db.list_courses(path)
    elif args.command == "add-section":
        return {"section_id": db.add_section(path, args.course_code, args.term,
                                             args.section_number, args.instructor, args.capacity)}
    elif args.command == "sections":
        return db.list_sections(path, args.term)
    elif args.command == "enroll":
        db.enroll(path, args.student_number, args.section_id)
    elif args.command == "drop":
        db.drop(path, args.student_number, args.section_id)
    elif args.command == "grade":
        db.set_grade(path, args.student_number, args.section_id, args.score)
    elif args.command == "transcript":
        return db.transcript(path, args.student_number)
    return {"message": "Done"}


def main() -> int:
    args = parser().parse_args()
    try:
        print(json.dumps(run(args), indent=2, ensure_ascii=False))
        return 0
    except db.DomainError as exc:
        print(f"Error: {exc}", file=sys.stderr)
    except sqlite3.IntegrityError as exc:
        print(f"Database constraint: {exc}", file=sys.stderr)
    except (sqlite3.OperationalError, OSError) as exc:
        print(f"Database/file error: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
