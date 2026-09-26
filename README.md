# University Enrollment Management System

A local university enrollment application built with **Python and SQL (SQLite)**. It provides a browser dashboard and a command-line interface for managing students, courses, class sections, enrollments, grades, and transcripts.

## Features

- Add, view, edit, and delete students and courses.
- Create class sections with an instructor, term, and seat capacity.
- Enroll students while preventing duplicate registrations and overbooking.
- Drop enrollments and release seats.
- Record grades and calculate a credit-weighted average on a 0–100 scale.
- View enrollment information through a browser dashboard or JSON output in the command line.

## Technologies

- **Python 3.10+** for application logic and the local web interface
- **SQLite and SQL** for relational data storage and queries
- **HTML and CSS** for the browser interface
- **Python `unittest`** for automated tests

No third-party packages or database server are required.

## Getting Started

Open a terminal in the project folder and run:

```bash
python web.py
```

The application opens your default browser automatically. If it does not, copy the URL printed after `OPEN THIS ADDRESS` into your browser. Keep the terminal open while using the application; press `Ctrl+C` to stop it.

The included `university.db` contains sample data, so you can explore the dashboard immediately.

To use the command-line interface:

```bash
python app.py students
python app.py sections
python app.py transcript S1001
```

## Database Design

The database contains four related tables: `students`, `courses`, `sections`, and `enrollments`. Primary and foreign keys maintain relationships, while SQL constraints help prevent invalid or duplicate data. Enrollment uses a transaction to check available seats before saving a registration.

## Tests

Run the automated tests with:

```bash
python -m unittest -v
```

## Project Scope

This is a **local demonstration application**. It does not include user authentication, timetable conflict checks, or prerequisite rules. It is not intended for public deployment without additional security and access controls.
