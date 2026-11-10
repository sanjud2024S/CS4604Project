"""
HireTrack - Flask REST API (backend)
CS 4604 Team 4 (Sanju Devakumaran, Ruthika Reddy)

Built on the CS 4604 DBMS Connection Demo (Huayu Liang, GTA, 10/15/2026):
same Flask + mysql-connector-python + .env structure, same CRUD endpoint
layout. The demo's React frontend is replaced by a single HTML page that
Flask serves itself, so only one server has to run.

Requirements covered here:
  the interface is connected to the database  -> GET  /api/status
  insert functionality                        -> POST /api/table/<table>
  delete functionality                        -> DELETE /api/table/<table>

The rest of the backend is split across three modules that register their
own routes on this app:

    auth.py        logging in, signing up, changing a password, and the
                   Admin screens for managing user accounts
    operations.py  the task screen behind every item on a role's menu
                   (apply to a job, post a job, schedule an interview,
                   approve a posting, make an offer, and so on)
    reports.py     the statistical reports, built with COUNT, MIN, MAX,
                   AVG and SUM

The generic table routes below are an administrator maintenance area;
ordinary users reach the data through the task screens instead.

Every statement sent to MySQL uses only constructs from the course notes:
    INSERT INTO ... VALUES      (Chapter 4)
    DELETE FROM ... WHERE       (Chapter 4)
    SELECT * FROM               (Chapter 4)
    SELECT COUNT(*) / MAX(...)  (Chapter 5 aggregate functions)

Run:
    pip install flask mysql-connector-python python-dotenv
    python app.py
    open http://127.0.0.1:5001
"""

import os
import secrets
import mysql.connector
from flask import Flask, jsonify, request, send_from_directory

import auth
import operations
import reports

# credentials live in .env, never in the source - Step 5.1 of the demo
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     int(os.getenv("DB_PORT", "3306")),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "hiretrack"),
}

HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=None)

# Signing key for the login session cookie. Set SECRET_KEY in .env so
# sessions survive a restart; otherwise a random one is used each run.
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)


# ===========================================================================
# SCHEMA - written out from the Phase 1 relational schema
# each column: (name, hint, required?, primary key?, referenced table)
# ===========================================================================
SCHEMA = {
 "DEPARTMENT": [
    ("DepartmentID",  "INT",            True,  True,  None),
    ("Name",          "VARCHAR(100)",   True,  False, None),
    ("Location",      "VARCHAR(100)",   True,  False, None)],

 "RECRUITER": [
    ("EmployeeID",    "INT",            True,  True,  None),
    ("Name",          "VARCHAR(100)",   True,  False, None),
    ("Email",         "VARCHAR(120)",   True,  False, None)],

 "CANDIDATE": [
    ("CandidateID",   "INT",            True,  True,  None),
    ("Name",          "VARCHAR(100)",   True,  False, None),
    ("Email",         "VARCHAR(120)",   True,  False, None),
    ("Type",          "Internal / External / Referral", True, False, None)],

 "HIRING_STATUS": [
    ("StatusID",      "INT",            True,  True,  None),
    ("StatusName",    "VARCHAR(40)",    True,  False, None),
    ("StageOrder",    "INT > 0",        True,  False, None)],

 "EMAIL_TEMPLATE": [
    ("TemplateID",    "INT",            True,  True,  None),
    ("Subject",       "VARCHAR(200)",   True,  False, None),
    ("Body",          "VARCHAR(500)",   True,  False, None)],

 "HIRING_MANAGER": [
    ("EmployeeID",    "INT",            True,  True,  None),
    ("Name",          "VARCHAR(100)",   True,  False, None),
    ("Email",         "VARCHAR(120)",   True,  False, None),
    ("DepartmentID",  "INT",            True,  False, "DEPARTMENT")],

 "ANALYTICS_REPORT": [
    ("ReportID",      "INT",            True,  True,  None),
    ("ReportType",    "VARCHAR(60)",    True,  False, None),
    ("GeneratedDate", "YYYY-MM-DD",     True,  False, None),
    ("GeneratedBy",   "INT",            True,  False, "RECRUITER")],

 "JOB_POSTING": [
    ("JobID",         "INT",            True,  True,  None),
    ("Title",         "VARCHAR(120)",   True,  False, None),
    ("Description",   "VARCHAR(500)",   False, False, None),
    ("DepartmentID",  "INT",            True,  False, "DEPARTMENT"),
    ("PostedBy",      "INT",            True,  False, "RECRUITER"),
    ("ApprovedBy",    "INT",            False, False, "HIRING_MANAGER")],

 "APPLICATION": [
    ("ApplicationID", "INT",            True,  True,  None),
    ("SubmissionDate","YYYY-MM-DD",     True,  False, None),
    ("ResumeLink",    "VARCHAR(255)",   False, False, None),
    ("CandidateID",   "INT",            True,  False, "CANDIDATE"),
    ("JobID",         "INT",            True,  False, "JOB_POSTING"),
    ("StatusID",      "INT",            True,  False, "HIRING_STATUS")],

 "INTERVIEW": [
    ("InterviewID",   "INT",            True,  True,  None),
    ("ScheduledDate", "YYYY-MM-DD HH:MM:SS", True, False, None),
    ("Feedback",      "VARCHAR(255)",   False, False, None),
    ("ApplicationID", "INT",            True,  False, "APPLICATION"),
    ("ConductedBy",   "INT",            True,  False, "HIRING_MANAGER")],

 "CANDIDATE_RANKING": [
    ("RankingID",     "INT",            True,  True,  None),
    ("Score",         "0.00 - 100.00",  True,  False, None),
    ("RankPosition",  "INT > 0",        True,  False, None),
    ("ApplicationID", "INT",            True,  False, "APPLICATION")],

 "JOB_OFFER": [
    ("OfferID",       "INT",            True,  True,  None),
    ("Salary",        "DECIMAL > 0",    True,  False, None),
    ("StartDate",     "YYYY-MM-DD",     True,  False, None),
    ("ApplicationID", "INT",            True,  False, "APPLICATION")],

 "SENT_EMAIL": [
    ("ApplicationID", "INT",            True,  True,  "APPLICATION"),
    ("TemplateID",    "INT",            True,  True,  "EMAIL_TEMPLATE"),
    ("SentDate",      "YYYY-MM-DD HH:MM:SS", True, True, None)],
}


def columns(table):
    return [c[0] for c in SCHEMA[table]]


def primary_key(table):
    return [c[0] for c in SCHEMA[table] if c[3]]


# =========================================================== SQL builders
def build_insert(table, values):
    """INSERT INTO t (cols) VALUES (...)   - Chapter 4.
    Blank fields are dropped so the column keeps its DEFAULT or NULL."""
    cols = [c for c in columns(table)
            if values.get(c) not in (None, "")]
    if not cols:
        raise ValueError("Nothing to insert - every field was left blank.")
    collist = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    return (f"INSERT INTO {table} ({collist}) VALUES ({marks})",
            tuple(values[c] for c in cols))


def build_delete(table, key):
    """DELETE FROM t WHERE key = ...   - Chapter 4.

    The demo deletes with /api/students/<id> because its table has a
    single-column key. SENT_EMAIL here has a three-column primary key,
    so the key is passed as name=value parameters instead."""
    pk = primary_key(table)
    missing = [c for c in pk if c not in key]
    if missing:
        raise ValueError(f"Missing key value(s): {', '.join(missing)}")
    where = " AND ".join(f"{c} = %s" for c in pk)
    return f"DELETE FROM {table} WHERE {where}", tuple(key[c] for c in pk)


def preview(sql, params):
    """Render a statement with its values inlined, for the page's SQL log."""
    parts = sql.split("%s")
    out = [parts[0]]
    for p, tail in zip(params, parts[1:]):
        lit = "NULL" if p is None else (
            str(p) if isinstance(p, (int, float))
            else "'" + str(p).replace("'", "''") + "'")
        out.append(lit)
        out.append(tail)
    return "".join(out)


# ================================================================ database
def connect():
    """Step 5 of the demo: Flask opens a MySQL connection with the
    credentials from .env."""
    return mysql.connector.connect(**DB_CONFIG)


# authentication, sign-up and user management live in auth.py. It must be
# registered first: it puts the login_required and roles_required guards on
# the app, and the two modules below use them.
auth.register(app, connect)

# the task screens behind each menu item, and the statistical reports
operations.register(app, connect)
reports.register(app, connect)


def jsonable(v):
    """Dates, datetimes and Decimals are not JSON types."""
    if v is None:
        return None
    if isinstance(v, (int, float, str)):
        return v
    return str(v)


# ================================================================== routes
@app.get("/")
def home():
    return send_from_directory(HERE, "index.html")


@app.get("/api/status")
def status():
    """Requirement 0 - proves the interface reached the database."""
    try:
        cx = connect()
        cur = cx.cursor()
        cur.execute("SELECT VERSION()")
        version = cur.fetchone()[0]
        cur.close(); cx.close()
        return jsonify({
            "connected": True,
            "dbms": f"MySQL {version}",
            "host": f"{DB_CONFIG['host']}:{DB_CONFIG['port']}",
            "database": DB_CONFIG["database"],
            "user": DB_CONFIG["user"],
            "interface": "Python + Flask REST API",
        })
    except mysql.connector.Error as err:
        return jsonify({"connected": False, "error": str(err)}), 500


@app.get("/api/tables")
@app.roles_required("Admin")
def tables(user):
    """The table layout, so the page can build its form and grid."""
    return jsonify({
        t: [{"name": n, "hint": h, "required": r, "pk": p, "fk": f}
            for (n, h, r, p, f) in cols]
        for t, cols in SCHEMA.items()
    })


@app.get("/api/table/<table>")
@app.roles_required("Admin")
def read(user, table):
    """READ - SELECT * FROM t  (Chapter 4), plus COUNT(*) and MAX(key)
    (Chapter 5 aggregates) so the page can show the row count and
    suggest the next free primary key."""
    if table not in SCHEMA:
        return jsonify({"error": f"Unknown table {table}"}), 404
    cx = connect(); cur = cx.cursor()
    cur.execute(f"SELECT * FROM {table}")
    rows = [[jsonable(v) for v in r] for r in cur.fetchall()]
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    total = cur.fetchone()[0]
    pk = primary_key(table)
    next_id = None
    if len(pk) == 1:
        cur.execute(f"SELECT MAX({pk[0]}) FROM {table}")
        top = cur.fetchone()[0]
        try:
            next_id = int(top) + 1
        except (TypeError, ValueError):
            next_id = 1
    cur.close(); cx.close()
    return jsonify({"columns": columns(table), "rows": rows,
                    "count": total, "next_id": next_id})


@app.post("/api/table/<table>")
@app.roles_required("Admin")
def create(user, table):
    """CREATE - INSERT INTO t (cols) VALUES (...)   (Chapter 4)."""
    if table not in SCHEMA:
        return jsonify({"error": f"Unknown table {table}"}), 404
    values = request.get_json(silent=True) or {}
    try:
        sql, params = build_insert(table, values)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    cx = connect(); cur = cx.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        before = cur.fetchone()[0]
        cur.execute(sql, params)
        cx.commit()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        after = cur.fetchone()[0]
        return jsonify({"ok": True, "sql": preview(sql, params),
                        "before": before, "after": after})
    except mysql.connector.Error as err:
        cx.rollback()
        return jsonify({"ok": False, "sql": preview(sql, params),
                        "error": err.msg, "errno": err.errno}), 400
    finally:
        cur.close(); cx.close()


@app.delete("/api/table/<table>")
@app.roles_required("Admin")
def destroy(user, table):
    """DELETE - DELETE FROM t WHERE key = ...   (Chapter 4).
    Key values arrive as query parameters, e.g.
        DELETE /api/DEPARTMENT?DepartmentID=21"""
    if table not in SCHEMA:
        return jsonify({"error": f"Unknown table {table}"}), 404
    try:
        sql, params = build_delete(table, request.args.to_dict())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    cx = connect(); cur = cx.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        before = cur.fetchone()[0]
        cur.execute(sql, params)
        cx.commit()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        after = cur.fetchone()[0]
        return jsonify({"ok": True, "sql": preview(sql, params),
                        "before": before, "after": after})
    except mysql.connector.Error as err:
        cx.rollback()
        return jsonify({"ok": False, "sql": preview(sql, params),
                        "error": err.msg, "errno": err.errno}), 400
    finally:
        cur.close(); cx.close()


if __name__ == "__main__":
    # The demo keeps credentials in .env. If DB_PASSWORD is empty or the
    # file was not found, ask for the password here instead of failing
    # with "Access denied ... using password: NO".
    if not DB_CONFIG["password"]:
        import getpass
        print("No DB_PASSWORD found in .env or the environment.")
        DB_CONFIG["password"] = getpass.getpass(
            f"MySQL password for '{DB_CONFIG['user']}': ")

    print("-" * 62)
    print("  HireTrack backend")
    print(f"  host     : {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"  user     : {DB_CONFIG['user']}")
    print(f"  database : {DB_CONFIG['database']}")
    print(f"  password : {'supplied' if DB_CONFIG['password'] else 'EMPTY'}")
    try:
        cx = connect(); cx.close()
        print("  status   : connection OK")
    except mysql.connector.Error as err:
        print(f"  status   : FAILED - {err}")
    print("  open       http://127.0.0.1:5001")
    print("-" * 62)

    app.run(port=5001, debug=False)
