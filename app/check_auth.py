#!/usr/bin/env python3
"""
HireTrack - authentication check
CS 4604 Team 4

Exercises the running Flask API against the real MySQL database and
prints what happened, so the user-support requirements can be seen
working end to end.

Start the server first in another Command Prompt:
    python app.py

Then run:
    python check_auth.py

Uses only the Python standard library.
"""

import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

BASE = "http://127.0.0.1:5001"
BAR = "=" * 70

opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(CookieJar()))


def call(method, path, body=None):
    """Returns (status, parsed json)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with opener.open(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}
    except urllib.error.URLError as e:
        print(f"\n  Could not reach {BASE} - is app.py running?\n  {e.reason}")
        sys.exit(1)


passed = failed = 0


def step(label, status, payload, expect):
    global passed, failed
    ok = status == expect
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}")
    print(f"         HTTP {status}   {json.dumps(payload)[:120]}")


print(BAR)
print("  HireTrack - user support check")
print(BAR)

print("\n1. The server is up and connected to MySQL")
s, d = call("GET", "/api/status")
step("GET /api/status", s, d, 200)

print("\n2. Nothing is reachable while signed out")
s, d = call("GET", "/api/me");            step("GET /api/me", s, d, 401)
s, d = call("GET", "/api/admin/users");   step("GET /api/admin/users", s, d, 401)

print("\n3. Logging in with a wrong password fails")
s, d = call("POST", "/api/login", {"username": "admin", "password": "nope"})
step("POST /api/login (bad password)", s, d, 401)

print("\n4. Logging in as the seeded admin")
s, d = call("POST", "/api/login", {"username": "admin", "password": "admin123"})
step("POST /api/login", s, d, 200)
if s != 200:
    print("\n  The admin password is no longer 'admin123'.")
    print("  Either it was already changed, or re-run hiretrack.sql.")
    sys.exit(1)
print(f"         role = {d.get('role')}   "
      f"must_change_password = {d.get('must_change_password')}")
print(f"         menu = {d.get('menu')}")

print("\n5. The forced password reset blocks every other action")
s, d = call("GET", "/api/admin/users")
step("GET /api/admin/users before the reset", s, d, 403)

print("\n6. Changing the password")
s, d = call("POST", "/api/change-password",
            {"old_password": "admin123", "new_password": "short"})
step("too short, rejected", s, d, 400)
s, d = call("POST", "/api/change-password",
            {"old_password": "admin123", "new_password": "HireTrack2026!"})
step("changed to a strong password", s, d, 200)

print("\n7. Admin routes are reachable now")
s, d = call("GET", "/api/admin/users")
step("GET /api/admin/users", s, d, 200)
for u in d.get("users", []):
    print(f"         {u['username']:<12} {u['role']:<16} {u['display_name']}")

print("\n8. Staff without a login, listed by name (not by ID)")
s, d = call("GET", "/api/admin/unlinked?role=Recruiter")
step("GET /api/admin/unlinked?role=Recruiter", s, d, 200)
for p in d.get("people", [])[:3]:
    print(f"         {p['name']}")
print(f"         ... {len(d.get('people', []))} recruiters without a login")

print("\n9. The admin creates another admin through the application")
s, d = call("POST", "/api/admin/create-user",
            {"username": "admin2", "password": "SecondAdmin2026",
             "role": "Admin"})
step("POST /api/admin/create-user", s, d, 200)

print("\n10. A candidate signs up for themselves")
call("POST", "/api/logout")
s, d = call("POST", "/api/signup",
            {"username": "newgrad", "password": "MyPassword2026",
             "name": "Nadia Osman", "email": "nosman@example.com"})
step("POST /api/signup", s, d, 200)
if s == 200:
    print(f"         signed in as {d.get('display_name')} ({d.get('role')})")
    print(f"         menu = {d.get('menu')}")

print("\n11. That candidate cannot reach admin routes")
s, d = call("GET", "/api/admin/users")
step("GET /api/admin/users as a Candidate", s, d, 403)

print("\n12. Logging out")
s, d = call("POST", "/api/logout");  step("POST /api/logout", s, d, 200)
s, d = call("GET", "/api/me");       step("GET /api/me afterwards", s, d, 401)

print("\n" + BAR)
print(f"  {passed} checks passed, {failed} failed")
print(BAR)
print("""
  Note: this run changed the admin password to 'HireTrack2026!' and
  created the users admin2 and newgrad. Re-run hiretrack.sql to reset.
""")
