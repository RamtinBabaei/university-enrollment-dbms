"""Dependency-free, localhost-only browser interface for the database project."""

from __future__ import annotations

import argparse
import html
import secrets
import sqlite3
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import db

ROOT = Path(__file__).resolve().parent
CSS = (ROOT / "style.css").read_bytes()


def e(value: object) -> str:
    return html.escape(str(value), quote=True)


def form(action: str, fields: str, token: str, label: str, kind: str = "") -> str:
    return (f'<form method="post" action="/{e(action)}">'
            f'<input type="hidden" name="csrf" value="{e(token)}">'
            f'{fields}<button class="button {kind}" type="submit">{e(label)}</button></form>')


class Handler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        # Log locally without exposing submitted student data.
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}")

    def send_html(self, content: str, status: int = 200) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; form-action 'self'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, page: str, message: str, error: bool = False) -> None:
        sep = "&" if "?" in page else "?"
        self.send_response(303)
        self.send_header("Location", f"{page}{sep}{'error' if error else 'notice'}={quote(message)}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def layout(self, title: str, active: str, body: str, query: dict) -> str:
        links = [("/", "نمای کلی"), ("/students", "دانشجویان"),
                 ("/courses", "درس‌ها"), ("/sections", "گروه‌ها"),
                 ("/enrollments", "ثبت‌نام‌ها"), ("/transcript", "کارنامه")]
        nav = "".join(
            f'<a href="{href}" class="{"active" if href == active else ""}">{label}</a>'
            for href, label in links
        )
        notice = ""
        for key, cls in (("notice", "success"), ("error", "error")):
            if query.get(key):
                notice = f'<div class="notice {cls}" role="status">{e(query[key][0])}</div>'
                break
        return f'''<!doctype html><html lang="fa" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} | سامانه ثبت‌نام دانشگاه</title>
<link rel="stylesheet" href="/style.css"></head><body>
<div class="shell"><aside class="sidebar"><div class="brand"><div class="logo">U</div><div><strong>UniLedger</strong><small>سامانه مدیریت آموزشی</small></div></div>
<nav aria-label="ناوبری اصلی">{nav}</nav><div class="sidebar-foot">Python · SQLite<br>نسخهٔ نمایشی محلی</div></aside>
<main class="main"><header class="topbar"><span>پنل مدیریت دانشگاه</span><span class="pill">● پایگاه داده فعال</span></header>
{notice}{body}<footer>UniLedger · پروژهٔ پایگاه داده با Python و SQL</footer></main></div></body></html>'''

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/style.css":
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(CSS)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(CSS)
            return
        query = parse_qs(url.query)
        pages = {"/": ("نمای کلی", self.dashboard), "/students": ("دانشجویان", self.students),
                 "/courses": ("درس‌ها", self.courses), "/sections": ("گروه‌ها", self.sections),
                 "/enrollments": ("ثبت‌نام‌ها", self.enrollments),
                 "/transcript": ("کارنامه", self.transcript)}
        if url.path not in pages:
            self.send_html(self.layout("یافت نشد", "", '<section class="card"><h1>صفحه پیدا نشد</h1></section>', {}), 404)
            return
        try:
            title, render = pages[url.path]
            self.send_html(self.layout(title, url.path, render(query), query))
        except (db.DomainError, sqlite3.Error, OSError, ValueError) as exc:
            self.send_html(self.layout("خطا", url.path,
                f'<section class="card"><h1>صفحه بارگذاری نشد</h1><p>{e(exc)}</p>'
                '<p>فایل پایگاه داده و پوشهٔ پروژه را بررسی کنید.</p></section>', {}), 500)
        except Exception:
            traceback.print_exc()
            self.send_html(self.layout("خطا", url.path,
                '<section class="card"><h1>صفحه بارگذاری نشد</h1>'
                '<p>جزئیات خطا در پنجرهٔ PowerShell چاپ شده است.</p></section>', {}), 500)

    def dashboard(self, _query: dict) -> str:
        students = db.list_students(self.server.db_path)
        courses = db.list_courses(self.server.db_path)
        sections = db.list_sections(self.server.db_path)
        enrollments = db.list_enrollments(self.server.db_path)
        cards = [("دانشجویان", len(students), "/students"), ("درس‌ها", len(courses), "/courses"),
                 ("گروه‌های درسی", len(sections), "/sections"), ("ثبت‌نام فعال", len(enrollments), "/enrollments")]
        summary = "".join(f'<a class="stat" href="{href}"><span>{name}</span><strong>{count}</strong><small>مشاهده ←</small></a>'
                          for name, count, href in cards)
        rows = "".join(
            f'<tr><td><span class="code">{e(s["code"])}</span> {e(s["title"])}</td>'
            f'<td>{e(s["term"])}</td><td>{e(s["instructor"])}</td>'
            f'<td><progress class="meter" value="{s["enrolled"]}" max="{s["capacity"]}"></progress>'
            f'{s["enrolled"]} از {s["capacity"]}</td></tr>' for s in sections[:6]
        ) or '<tr><td colspan="4" class="empty">هنوز گروهی ثبت نشده است.</td></tr>'
        return f'''<div class="hero"><div><span class="eyebrow">UNIVERSITY DATABASE SYSTEM</span>
<h1>مدیریت آموزش، در یک نگاه.</h1><p>دانشجویان، درس‌ها، ظرفیت گروه‌ها و کارنامه را از همین پنل مدیریت کنید.</p>
<a class="button light" href="/enrollments">مدیریت ثبت‌نام‌ها ←</a></div><div class="hero-art">01 <span> / </span> 06</div></div>
<div class="stats">{summary}</div><section class="card"><div class="section-head"><div><h2>وضعیت گروه‌ها</h2><p>ظرفیت و تعداد ثبت‌نام‌های فعال</p></div><a href="/sections">همهٔ گروه‌ها ←</a></div>
<div class="table-wrap"><table><thead><tr><th>درس</th><th>ترم</th><th>استاد</th><th>ظرفیت پرشده</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''

    def students(self, _query: dict) -> str:
        rows = db.list_students(self.server.db_path)
        token = self.server.csrf
        fields = '<label>شماره دانشجویی<input name="number" required placeholder="S1003"></label><label>نام کامل<input name="name" required placeholder="Sara Ahmadi"></label><label>ایمیل<input type="email" name="email" required placeholder="sara@example.com"></label>'
        add = form("add-student", fields, token, "افزودن دانشجو")
        body = "".join(
            f'<tr><td><span class="code">{e(r["student_number"])}</span></td><td>{e(r["full_name"])}</td><td>{e(r["email"])}</td><td class="actions">'
            + '<details><summary>ویرایش</summary>'+form("edit-student", f'<input type="hidden" name="number" value="{e(r["student_number"])}"><label>نام<input name="name" required value="{e(r["full_name"])}"></label><label>ایمیل<input type="email" name="email" required value="{e(r["email"])}"></label>', token, "ذخیره")+'</details>'
            +form("delete-student", f'<input type="hidden" name="number" value="{e(r["student_number"])}">', token, "حذف", "danger")+"</td></tr>" for r in rows
        ) or '<tr><td colspan="4" class="empty">دانشجویی ثبت نشده است.</td></tr>'
        return self.page("دانشجویان", "اطلاعات دانشجو را اضافه یا ویرایش کنید.", "دانشجوی جدید", add,
                         f'<table><thead><tr><th>شماره</th><th>نام</th><th>ایمیل</th><th>عملیات</th></tr></thead><tbody>{body}</tbody></table>')

    def courses(self, _query: dict) -> str:
        rows = db.list_courses(self.server.db_path)
        token = self.server.csrf
        fields = '<label>کد درس<input name="code" required placeholder="CS303"></label><label>عنوان<input name="title" required placeholder="Human Computer Interaction"></label><label>واحد<input type="number" name="credits" min="1" max="6" required value="3"></label>'
        add = form("add-course", fields, token, "افزودن درس")
        body = "".join(
            f'<tr><td><span class="code">{e(r["code"])}</span></td><td>{e(r["title"])}</td><td>{r["credits"]}</td><td class="actions">'
            + '<details><summary>ویرایش</summary>'+form("edit-course", f'<input type="hidden" name="code" value="{e(r["code"])}"><label>عنوان<input name="title" required value="{e(r["title"])}"></label><label>واحد<input type="number" name="credits" min="1" max="6" required value="{r["credits"]}"></label>', token, "ذخیره")+'</details>'
            +form("delete-course", f'<input type="hidden" name="code" value="{e(r["code"])}">', token, "حذف", "danger")+"</td></tr>" for r in rows
        ) or '<tr><td colspan="4" class="empty">درسی ثبت نشده است.</td></tr>'
        return self.page("درس‌ها", "فهرست درس‌ها و تعداد واحد آن‌ها.", "درس جدید", add,
                         f'<table><thead><tr><th>کد درس</th><th>عنوان</th><th>واحد</th><th>عملیات</th></tr></thead><tbody>{body}</tbody></table>')

    def sections(self, _query: dict) -> str:
        sections = db.list_sections(self.server.db_path)
        courses = db.list_courses(self.server.db_path)
        options = "".join(f'<option value="{e(c["code"])}">{e(c["code"])} · {e(c["title"])}</option>' for c in courses)
        fields = f'<label>درس<select name="course_code" required>{options}</select></label><label>ترم<input name="term" required value="2026-Fall"></label><label>شماره گروه<input type="number" name="section_number" min="1" required value="1"></label><label>استاد<input name="instructor" required placeholder="Dr. Example"></label><label>ظرفیت<input type="number" name="capacity" min="1" required value="25"></label>'
        add = form("add-section", fields, self.server.csrf, "ایجاد گروه") if courses else '<p class="muted">ابتدا یک درس در بخش «درس‌ها» بسازید.</p>'
        rows = "".join(
            f'<tr><td><span class="code">#{r["id"]}</span></td><td>{e(r["code"])} · {e(r["title"])}</td>'
            f'<td>{e(r["term"])} / گروه {r["section_number"]}</td><td>{e(r["instructor"])}</td>'
            f'<td>{r["enrolled"]} / {r["capacity"]}</td><td><span class="badge {"full" if r["seats_left"] == 0 else "open"}">{"تکمیل" if r["seats_left"] == 0 else str(r["seats_left"]) + " جای خالی"}</span></td></tr>'
            for r in sections
        ) or '<tr><td colspan="6" class="empty">گروهی ثبت نشده است.</td></tr>'
        return self.page("گروه‌های درسی", "ارائهٔ درس‌ها، استادان و ظرفیت هر گروه.", "گروه جدید", add,
                         f'<table><thead><tr><th>شناسه</th><th>درس</th><th>ترم / گروه</th><th>استاد</th><th>ثبت‌نام</th><th>وضعیت</th></tr></thead><tbody>{rows}</tbody></table>')

    def enrollments(self, _query: dict) -> str:
        students = db.list_students(self.server.db_path)
        sections = db.list_sections(self.server.db_path)
        records = db.list_enrollments(self.server.db_path)
        student_options = "".join(f'<option value="{e(s["student_number"])}">{e(s["student_number"])} · {e(s["full_name"])}</option>' for s in students)
        section_options = "".join(f'<option value="{s["id"]}">#{s["id"]} · {e(s["code"])} · {e(s["term"])} · {s["seats_left"]} جای خالی</option>' for s in sections)
        fields = f'<label>دانشجو<select name="student_number" required>{student_options}</select></label><label>گروه<select name="section_id" required>{section_options}</select></label>'
        add = form("enroll", fields, self.server.csrf, "ثبت‌نام") if students and sections else '<p class="muted">ابتدا دانشجو و گروه درسی بسازید.</p>'
        token = self.server.csrf
        rows = "".join(
            f'<tr><td><span class="code">{e(r["student_number"])}</span><br>{e(r["full_name"])}</td>'
            f'<td>{e(r["code"])} · {e(r["title"])}</td><td>{e(r["term"])} / گروه {r["section_number"]}</td>'
            f'<td>{"—" if r["grade"] is None else e(r["grade"])}</td><td class="actions">'
            +form("grade", f'<input type="hidden" name="student_number" value="{e(r["student_number"])}"><input type="hidden" name="section_id" value="{r["section_id"]}"><input class="score" type="number" name="score" min="0" max="100" step="0.01" required aria-label="نمره" placeholder="نمره" value="{e(r["grade"]) if r["grade"] is not None else ""}">', token, "ثبت نمره", "small")
            +form("drop", f'<input type="hidden" name="student_number" value="{e(r["student_number"])}"><input type="hidden" name="section_id" value="{r["section_id"]}">', token, "انصراف", "danger")+"</td></tr>" for r in records
        ) or '<tr><td colspan="5" class="empty">ثبت‌نام فعالی وجود ندارد.</td></tr>'
        return self.page("ثبت‌نام‌ها", "ثبت‌نام، انصراف و ثبت نمرهٔ دانشجویان.", "ثبت‌نام جدید", add,
                         f'<table><thead><tr><th>دانشجو</th><th>درس</th><th>ترم</th><th>نمره</th><th>عملیات</th></tr></thead><tbody>{rows}</tbody></table>')

    def transcript(self, query: dict) -> str:
        students = db.list_students(self.server.db_path)
        number = query.get("student", [students[0]["student_number"] if students else ""])[0]
        options = "".join(f'<option value="{e(s["student_number"])}" {"selected" if s["student_number"] == number else ""}>{e(s["student_number"])} · {e(s["full_name"])}</option>' for s in students)
        picker = f'<form method="get" action="/transcript" class="picker"><label>دانشجو<select name="student">{options}</select></label><button class="button" type="submit">نمایش کارنامه</button></form>' if students else '<p class="muted">هنوز دانشجویی ثبت نشده است.</p>'
        detail = ""
        if number:
            try:
                report = db.transcript(self.server.db_path, number)
                rows = "".join(f'<tr><td><span class="code">{e(r["code"])}</span></td><td>{e(r["title"])}</td><td>{e(r["term"])}</td><td>{r["credits"]}</td><td>{"ثبت نشده" if r["grade"] is None else e(r["grade"])}</td></tr>' for r in report["courses"])
                rows = rows or '<tr><td colspan="5" class="empty">درس فعالی وجود ندارد.</td></tr>'
                average = "—" if report["weighted_average_100"] is None else e(report["weighted_average_100"])
                detail = f'<div class="report-head"><div><span class="eyebrow">STUDENT RECORD</span><h2>{e(report["student"]["full_name"])}</h2><p>شماره دانشجویی: {e(number)}</p></div><div class="average"><small>میانگین وزنی از ۱۰۰</small><strong>{average}</strong><small>{report["graded_credits"]} واحد نمره‌دار</small></div></div><div class="table-wrap"><table><thead><tr><th>کد</th><th>درس</th><th>ترم</th><th>واحد</th><th>نمره</th></tr></thead><tbody>{rows}</tbody></table></div><p class="hint">فقط درس‌های دارای نمره در میانگین حساب می‌شوند. این عدد معدل مقیاس ۴ نیست.</p>'
            except db.DomainError as exc:
                detail = f'<p class="notice error">{e(exc)}</p>'
        return f'<div class="page-title"><span class="eyebrow">REPORTS / TRANSCRIPT</span><h1>کارنامهٔ دانشجو</h1><p>درس‌های فعال و میانگین وزنی نمرات.</p></div><section class="card">{picker}</section><section class="card">{detail}</section>'

    def page(self, title: str, subtitle: str, form_title: str, add_form: str, table: str) -> str:
        return (f'<div class="page-title"><span class="eyebrow">DATABASE / MANAGEMENT</span><h1>{e(title)}</h1><p>{e(subtitle)}</p></div>'
                f'<section class="card form-card"><h2>{e(form_title)}</h2>{add_form}</section>'
                f'<section class="card"><div class="section-head"><h2>فهرست {e(title)}</h2></div><div class="table-wrap">{table}</div></section>')

    def do_POST(self) -> None:
        action = urlsplit(self.path).path.lstrip("/")
        page = {"add-student": "/students", "edit-student": "/students", "delete-student": "/students",
                "add-course": "/courses", "edit-course": "/courses", "delete-course": "/courses",
                "add-section": "/sections", "enroll": "/enrollments", "drop": "/enrollments",
                "grade": "/enrollments"}.get(action)
        if page is None:
            self.send_html(self.layout("یافت نشد", "", '<section class="card"><h1>صفحه پیدا نشد</h1></section>', {}), 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384 or self.headers.get("Content-Type", "").split(";")[0] != "application/x-www-form-urlencoded":
                raise db.DomainError("درخواست نامعتبر است.")
            values = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            if not secrets.compare_digest(values.get("csrf", [""])[0], self.server.csrf):
                raise db.DomainError("اعتبار فرم منقضی شده است؛ صفحه را تازه‌سازی کنید.")
            def v(key: str) -> str:
                return values.get(key, [""])[0].strip()
            path = self.server.db_path
            if action == "add-student":
                db.add_student(path, v("number"), v("name"), v("email"))
            elif action == "edit-student":
                db.update_student(path, v("number"), v("name"), v("email"))
            elif action == "delete-student":
                db.delete_student(path, v("number"))
            elif action == "add-course":
                db.add_course(path, v("code"), v("title"), int(v("credits")))
            elif action == "edit-course":
                db.update_course(path, v("code"), v("title"), int(v("credits")))
            elif action == "delete-course":
                db.delete_course(path, v("code"))
            elif action == "add-section":
                db.add_section(path, v("course_code"), v("term"), int(v("section_number")),
                               v("instructor"), int(v("capacity")))
            elif action == "enroll":
                db.enroll(path, v("student_number"), int(v("section_id")))
            elif action == "drop":
                db.drop(path, v("student_number"), int(v("section_id")))
            elif action == "grade":
                db.set_grade(path, v("student_number"), int(v("section_id")), float(v("score")))
            self.redirect(page, "عملیات با موفقیت انجام شد.")
        except (ValueError, UnicodeError, db.DomainError, sqlite3.Error, OSError) as exc:
            self.redirect(page, f"عملیات انجام نشد: {exc}", error=True)


def make_server(db_path: Path, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    if not db_path.is_file():
        db.initialize(db_path)
    server = ThreadingHTTPServer((host, port), Handler)
    server.db_path = db_path
    server.csrf = secrets.token_urlsafe(32)
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Local browser UI for university enrollment")
    parser.add_argument("--db", type=Path, default=ROOT / "university.db")
    parser.add_argument("--port", type=int, default=0,
                        help="Port number; default chooses a free local port")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser tab automatically")
    args = parser.parse_args()
    try:
        server = make_server(args.db, port=args.port)
    except (OSError, sqlite3.Error) as exc:
        parser.error(f"Could not start: {exc}. Try --port 0 or check the database path.")
    with server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"OPEN THIS ADDRESS: {url}", flush=True)
        print("Keep this window open; press Ctrl+C to stop.", flush=True)
        if not args.no_browser:
            opener = threading.Timer(0.3, lambda: webbrowser.open_new_tab(url))
            opener.daemon = True
            opener.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
