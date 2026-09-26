# University Enrollment Database Management System

A local browser application with an optional command-line interface, built with **Python 3.10+** and **SQL (SQLite)**. It manages students, courses, course sections, enrollment, capacity, grades, and transcripts. No third-party packages or database server are required.

## What it does

1. Creates a relational database from `schema.sql`.
2. Adds, lists, edits, and deletes students and courses.
3. Creates course sections with a term, instructor, and seat capacity.
4. Enrolls students and rejects duplicate enrollment, two sections of the same course in one term, or full sections.
5. Drops enrollments, assigns scores out of 100, and produces a credit-weighted transcript.
6. Uses transactions, foreign keys, uniqueness checks, SQL constraints, indexes, joins, and parameterized queries.

The word “DBMS” here describes an **application that manages records using a database**. It is not an implementation of a database engine such as SQLite or PostgreSQL.

## Run the browser application (recommended)

Extract the ZIP and open a terminal in the `university_enrollment` folder. On Windows PowerShell:

```powershell
python web.py
```

The program selects an available local port, prints the exact `OPEN THIS ADDRESS` URL, and opens your default browser automatically. If no tab opens, copy **the exact address printed in PowerShell** into Chrome; do not reuse an address from an earlier run. Keep the terminal open while using the application. Press `Ctrl+C` to stop. The included `university.db` contains sample data. The interface has a dashboard and pages for students, courses, sections, enrollments, grades, and transcripts. You can edit and delete unlinked students/courses, while related data is protected by database foreign keys.

To run on another port or with an independent database:

```powershell
python web.py --port 8081 --db fresh.db
```

An absent database path creates empty tables. For a separate database with sample records, run `python app.py --db fresh.db seed` before starting the web interface. The server binds only to `127.0.0.1`, so it is intended for local demos, not public deployment.

If Chrome displays an empty page, close the earlier terminal/server, start `python web.py` again, and use the newly printed URL. If it still fails, send the text shown in PowerShell, the complete browser address, and a screenshot. The application now displays database errors on a visible error page instead of closing the connection silently.

## Optional command-line interface

On Windows, `py` may be used instead of `python`.

```bash
python --version
python app.py students
python app.py courses
python app.py sections --term 2026-Fall
python app.py transcript S1001
```

The archive already contains `university.db` with example records. To create a **separate** populated database, run `python app.py --db fresh.db seed`. To start a separate empty database, run `python app.py --db fresh.db init` instead. `seed` requires an empty database and should only be run once for a given database.

### Commands

```bash
python app.py --help
python app.py add-student S1003 "Sara Ahmadi" sara@example.com
python app.py edit-student S1003 "Sara A. Ahmadi" sara.a@example.com
python app.py delete-student S1003
python app.py add-course CS303 "Human Computer Interaction" 3
python app.py edit-course CS303 "Human-Computer Interaction" 3
python app.py delete-course CS303
python app.py add-section CS303 2026-Fall 1 "Dr. Example" 25
python app.py sections
python app.py enroll S1003 3
python app.py grade S1003 3 87.5
python app.py transcript S1003
python app.py drop S1003 3
```

The enrollment example requires S1003 to exist and assumes the new section gets ID 3 in the seeded database. Use the `section_id` returned by `add-section` on your database. A student/course with linked records cannot be deleted until those records are removed; enrollment history is retained, and the CLI does not delete sections. Use a fresh database for an entirely new dataset.

To use a separate database, place `--db PATH` **before** the command:

```bash
python app.py --db my_data.db init
python app.py --db my_data.db students
```

Output is JSON, so it can also be consumed by another program. Expected validation failures are shown on stderr and return exit code 1.

## Database design

| Table | Primary key | Important relationships and rules |
| --- | --- | --- |
| `students` | `id` | Unique student number and email |
| `courses` | `id` | Unique code; credits 1–6 |
| `sections` | `id` | `course_id` → courses; unique course, term, section number; positive capacity |
| `enrollments` | `id` | `student_id` → students; `section_id` → sections; unique student and section; valid status and grade |

The relationships are `courses 1:N sections`, `students 1:N enrollments`, and `sections 1:N enrollments`. An enrollment links a student to a section. Dropping changes its status, preserving its record and releasing the seat. Re-enrollment reactivates the same record. The transcript lists currently active enrollments; its average includes only courses with grades and weights them by credits. This is a 0–100 average, not a 4.0 GPA.

The `BEGIN IMMEDIATE` transaction makes the check for free seats and the insertion one atomic operation across SQLite processes. The application also checks one active section per course per term; this is an application rule, while the same-section uniqueness is enforced by the schema.

## Files

- `schema.sql`: SQL schema, foreign keys, constraints, and indexes.
- `db.py`: database operations and business rules.
- `app.py`: command-line interface and example-data loader.
- `web.py`, `style.css`: local browser interface and styling.
- `test_db.py`, `test_web.py`: tests for business rules and browser form workflows.
- `GUIDE_FA.md`: Persian explanation and presentation notes.
- `example_output.json`: captured reports from the example database.

## Test

```bash
python -m unittest -v
```

## Scope and next steps

This is a local demonstration application with transactional seat booking. It has no authentication, timetable conflict detection, prerequisite rules, or department-specific grading scale. A future extension could add a production API and PostgreSQL, plus role-based permissions and an explicit academic grading policy.

**Portfolio description (use only after you have reviewed and can explain the code):** Built a Python/SQLite university enrollment application with a browser dashboard and CLI, relational schema, CRUD forms, transactional capacity checks, grade management, and credit-weighted reporting; verified key business rules with automated tests.
