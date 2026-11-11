"""
HireTrack - authentication and user management
CS 4604 Team 4 (Sanju Devakumaran, Ruthika Reddy)

Final phase, user support requirement:
  - different types of users: Admin, Recruiter, Hiring Manager, Candidate
  - no hardcoded passwords; accounts live in the USER_ACCOUNT table
  - every user has a username and a password
  - sign up, log in, log out, change password
  - only the first admin is created by hand (in hiretrack.sql); after
    that an admin creates other admins through the application
  - passwords are stored as a salted pbkdf2 hash, never in plain text

Only SQL from the course notes is used:
    SELECT ... FROM ... WHERE      (Chapter 4)
    INSERT INTO ... VALUES         (Chapter 4)
    UPDATE ... SET ... WHERE       (Chapter 4)
    SELECT MAX(...), COUNT(*)      (Chapter 5 aggregates)
    NOT IN (nested query)          (Chapter 5)

This module is imported by app.py; it registers its routes on the app.
"""

from functools import wraps

import mysql.connector
from flask import jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash

MIN_PASSWORD_LENGTH = 8

# Which menu items each role may reach. The frontend renders these as a
# task menu; the backend uses the same table to guard its routes.
ROLE_MENUS = {
    "Recruiter": [
        "Post a job", "Review applications", "Schedule interviews",
        "Send status emails", "View ranked candidates", "Reports",
    ],
    "Hiring Manager": [
        "Approve postings", "Review shortlist",
        "Record interview feedback", "Make offers", "Reports",
    ],
    "Candidate": [
        "Browse jobs", "Apply to a job", "Track my applications",
        "My interviews", "Reports",
    ],
    "Admin": [
        "Manage users", "Create an admin",
        "Manage email templates", "Manage departments", "Reports",
    ],
}

# which column of USER_ACCOUNT links to which person table
LINK = {
    "Candidate":      ("CandidateID", "CANDIDATE",      "CandidateID"),
    "Recruiter":      ("RecruiterID", "RECRUITER",      "EmployeeID"),
    "Hiring Manager": ("ManagerID",   "HIRING_MANAGER", "EmployeeID"),
}


# ----------------------------------------------------------------- helpers
def _next_id(cur, table, pk):
    cur.execute(f"SELECT MAX({pk}) FROM {table}")
    top = cur.fetchone()[0]
    try:
        return int(top) + 1
    except (TypeError, ValueError):
        return 1


def _display_name(cur, role, candidate_id, recruiter_id, manager_id):
    """The person's real name, so the interface never shows a bare ID."""
    if role == "Admin":
        return "Administrator"
    col, table, pk = LINK[role]
    person_id = {"CandidateID": candidate_id,
                 "RecruiterID": recruiter_id,
                 "ManagerID": manager_id}[col]
    cur.execute(f"SELECT Name FROM {table} WHERE {pk} = %s", (person_id,))
    row = cur.fetchone()
    return row[0] if row else "Unknown"


def _load_user(cur, user_id):
    cur.execute("""SELECT UserID, Username, Role, MustChangePassword,
                          CandidateID, RecruiterID, ManagerID
                   FROM   USER_ACCOUNT
                   WHERE  UserID = %s""", (user_id,))
    r = cur.fetchone()
    if not r:
        return None
    return {
        "user_id": r[0], "username": r[1], "role": r[2],
        "must_change_password": bool(r[3]),
        "display_name": _display_name(cur, r[2], r[4], r[5], r[6]),
        "menu": ROLE_MENUS.get(r[2], []),
        # which person this login belongs to. operations.py uses these so
        # a recruiter only ever sees their own postings, a candidate only
        # their own applications, and so on. Exactly one is set, except
        # for an Admin, where all three are NULL.
        "candidate_id": r[4],
        "recruiter_id": r[5],
        "manager_id": r[6],
    }


def register(app, connect):
    """Attach the auth routes to the Flask app.
    `connect` is app.py's function that opens a MySQL connection."""

    # ---- guards --------------------------------------------------------
    def current_user():
        uid = session.get("user_id")
        if not uid:
            return None
        cx = connect(); cur = cx.cursor()
        try:
            return _load_user(cur, uid)
        finally:
            cur.close(); cx.close()

    def login_required(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            user = current_user()
            if not user:
                return jsonify({"error": "Not signed in."}), 401
            # a forced password reset blocks everything else
            if user["must_change_password"] and fn.__name__ != "change_password":
                return jsonify({"error": "Password change required.",
                                "must_change_password": True}), 403
            return fn(user, *a, **kw)
        return wrapper

    def roles_required(*allowed):
        def deco(fn):
            @wraps(fn)
            @login_required
            def wrapper(user, *a, **kw):
                if user["role"] not in allowed:
                    return jsonify({
                        "error": f"This action is for "
                                 f"{' or '.join(allowed)} users."}), 403
                return fn(user, *a, **kw)
            return wrapper
        return deco

    app.current_user = current_user
    app.login_required = login_required
    app.roles_required = roles_required

    # ---- log in / out --------------------------------------------------
    @app.post("/api/login")
    def login():
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            return jsonify({"error": "Enter a username and a password."}), 400

        cx = connect(); cur = cx.cursor()
        try:
            cur.execute("""SELECT UserID, PasswordHash
                           FROM   USER_ACCOUNT
                           WHERE  Username = %s""", (username,))
            row = cur.fetchone()
            # the same message either way, so the form cannot be used to
            # discover which usernames exist
            if not row or not check_password_hash(row[1], password):
                return jsonify({"error": "Incorrect username or password."}), 401
            session.clear()
            session["user_id"] = row[0]
            user = _load_user(cur, row[0])
            return jsonify({"ok": True, **user})
        finally:
            cur.close(); cx.close()

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/me")
    def me():
        user = current_user()
        if not user:
            return jsonify({"error": "Not signed in."}), 401
        return jsonify(user)

    # ---- sign up -------------------------------------------------------
    @app.post("/api/signup")
    def signup():
        """Public sign-up creates a Candidate: a new person applying for
        jobs. Staff accounts are created by an admin instead, so nobody
        can grant themselves recruiter access."""
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        name     = (data.get("name") or "").strip()
        email    = (data.get("email") or "").strip()

        if not all([username, password, name, email]):
            return jsonify({"error": "All fields are required."}), 400
        if len(password) < MIN_PASSWORD_LENGTH:
            return jsonify({"error": f"Password must be at least "
                                     f"{MIN_PASSWORD_LENGTH} characters."}), 400

        cx = connect(); cur = cx.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM USER_ACCOUNT WHERE Username = %s",
                        (username,))
            if cur.fetchone()[0]:
                return jsonify({"error": "That username is already taken."}), 400
            cur.execute("SELECT COUNT(*) FROM CANDIDATE WHERE Email = %s", (email,))
            if cur.fetchone()[0]:
                return jsonify({"error": "That email is already registered."}), 400

            cand_id = _next_id(cur, "CANDIDATE", "CandidateID")
            cur.execute("""INSERT INTO CANDIDATE (CandidateID, Name, Email, Type)
                           VALUES (%s, %s, %s, 'External')""",
                        (cand_id, name, email))
            user_id = _next_id(cur, "USER_ACCOUNT", "UserID")
            cur.execute("""INSERT INTO USER_ACCOUNT
                             (UserID, Username, PasswordHash, Role,
                              MustChangePassword, CandidateID)
                           VALUES (%s, %s, %s, 'Candidate', 0, %s)""",
                        (user_id, username,
                         generate_password_hash(password, method="pbkdf2:sha256"),
                         cand_id))
            cx.commit()
            session.clear()
            session["user_id"] = user_id
            return jsonify({"ok": True, **_load_user(cur, user_id)})
        except mysql.connector.Error as err:
            cx.rollback()
            return jsonify({"error": err.msg}), 400
        finally:
            cur.close(); cx.close()

    # ---- change password -----------------------------------------------
    @app.post("/api/change-password")
    @login_required
    def change_password(user):
        data = request.get_json(silent=True) or {}
        old = data.get("old_password") or ""
        new = data.get("new_password") or ""
        if len(new) < MIN_PASSWORD_LENGTH:
            return jsonify({"error": f"New password must be at least "
                                     f"{MIN_PASSWORD_LENGTH} characters."}), 400
        if old == new:
            return jsonify({"error": "The new password must be different."}), 400

        cx = connect(); cur = cx.cursor()
        try:
            cur.execute("SELECT PasswordHash FROM USER_ACCOUNT WHERE UserID = %s",
                        (user["user_id"],))
            stored = cur.fetchone()[0]
            if not check_password_hash(stored, old):
                return jsonify({"error": "Current password is incorrect."}), 400
            cur.execute("""UPDATE USER_ACCOUNT
                           SET    PasswordHash = %s, MustChangePassword = 0
                           WHERE  UserID = %s""",
                        (generate_password_hash(new, method="pbkdf2:sha256"),
                         user["user_id"]))
            cx.commit()
            return jsonify({"ok": True, **_load_user(cur, user["user_id"])})
        finally:
            cur.close(); cx.close()

    # ---- admin: manage users -------------------------------------------
    @app.get("/api/admin/users")
    @roles_required("Admin")
    def list_users(user):
        cx = connect(); cur = cx.cursor()
        try:
            cur.execute("""SELECT UserID, Username, Role, MustChangePassword,
                                  CandidateID, RecruiterID, ManagerID
                           FROM   USER_ACCOUNT
                           ORDER BY Role, Username""")
            rows = cur.fetchall()
            out = [{"user_id": r[0], "username": r[1], "role": r[2],
                    "must_change_password": bool(r[3]),
                    "display_name": _display_name(cur, r[2], r[4], r[5], r[6])}
                   for r in rows]
            return jsonify({"users": out})
        finally:
            cur.close(); cx.close()

    @app.get("/api/admin/unlinked")
    @roles_required("Admin")
    def unlinked_people(user):
        """Staff who do not have a login yet, by name, so the admin picks
        a person from a list instead of typing an ID."""
        role = request.args.get("role", "Recruiter")
        if role not in LINK:
            return jsonify({"error": f"Unknown role {role}"}), 400
        col, table, pk = LINK[role]
        cx = connect(); cur = cx.cursor()
        try:
            cur.execute(f"""SELECT {pk}, Name
                            FROM   {table}
                            WHERE  {pk} NOT IN (SELECT {col}
                                                FROM   USER_ACCOUNT
                                                WHERE  {col} IS NOT NULL)
                            ORDER BY Name""")
            return jsonify({"people": [{"id": r[0], "name": r[1]}
                                       for r in cur.fetchall()]})
        finally:
            cur.close(); cx.close()

    @app.post("/api/admin/create-user")
    @roles_required("Admin")
    def create_user(user):
        """An admin creates another admin, or a login for existing staff."""
        data = request.get_json(silent=True) or {}
        username  = (data.get("username") or "").strip()
        password  = data.get("password") or ""
        role      = data.get("role") or ""
        person_id = data.get("person_id")

        if role not in ("Admin", "Recruiter", "Hiring Manager"):
            return jsonify({"error": "Role must be Admin, Recruiter or "
                                     "Hiring Manager."}), 400
        if not username or not password:
            return jsonify({"error": "Enter a username and a password."}), 400
        if len(password) < MIN_PASSWORD_LENGTH:
            return jsonify({"error": f"Password must be at least "
                                     f"{MIN_PASSWORD_LENGTH} characters."}), 400
        if role != "Admin" and not person_id:
            return jsonify({"error": "Choose the person this login belongs to."}), 400

        cx = connect(); cur = cx.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM USER_ACCOUNT WHERE Username = %s",
                        (username,))
            if cur.fetchone()[0]:
                return jsonify({"error": "That username is already taken."}), 400

            cand = rec = mgr = None
            if role == "Recruiter":
                rec = person_id
            elif role == "Hiring Manager":
                mgr = person_id

            user_id = _next_id(cur, "USER_ACCOUNT", "UserID")
            cur.execute("""INSERT INTO USER_ACCOUNT
                             (UserID, Username, PasswordHash, Role,
                              MustChangePassword, CandidateID, RecruiterID,
                              ManagerID)
                           VALUES (%s, %s, %s, %s, 1, %s, %s, %s)""",
                        (user_id, username,
                         generate_password_hash(password, method="pbkdf2:sha256"),
                         role, cand, rec, mgr))
            cx.commit()
            return jsonify({"ok": True, "user_id": user_id,
                            "username": username, "role": role,
                            "note": "They will be asked to change this "
                                    "password at first login."})
        except mysql.connector.Error as err:
            cx.rollback()
            return jsonify({"error": err.msg}), 400
        finally:
            cur.close(); cx.close()

    @app.get("/api/menu")
    @login_required
    def menu(user):
        """What this user is allowed to do, for the role-based shell."""
        return jsonify({"role": user["role"],
                        "display_name": user["display_name"],
                        "items": user["menu"]})
