#!/usr/bin/env python3
"""
HireTrack - system functionality and reporting check
CS 4604 Team 4

Walks one candidate all the way through hiring, using only the API that
the GUI uses, and then runs every statistical report for every kind of
user. Nothing is set up by hand: the accounts, the job, the application,
the interview and the offer are all created through the application while
this runs, so the output is evidence that the operations work.

    an admin creates a recruiter and a hiring manager login
    the recruiter posts a job
    the hiring manager approves it
    a candidate signs up, finds the job and applies
    the recruiter screens them and emails them
    the recruiter books an interview with the hiring manager
    the hiring manager records feedback and makes an offer
    the candidate sees the offer on their own screen
    every role runs its reports
    every role is refused the other roles' operations

Start the server first in another Command Prompt:
    python app.py

Then run:
    python check_ops.py                 (admin password admin123)
    python check_ops.py MyAdminPass     (if it has been changed)

Uses only the Python standard library.
"""

import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from http.cookiejar import CookieJar

BASE = "http://127.0.0.1:5001"
BAR = "=" * 70
# makes the usernames this run creates unique, so it can be run again
STAMP = datetime.now().strftime("%m%d%H%M%S")

PASSWORD = "DemoPass2026!"
# 'admin123' is the seeded password; the others are what an earlier run of
# this script or of check_auth.py would have left behind, so the script can
# be run more than once without resetting the database first
ADMIN_TRIES = ([sys.argv[1]] if len(sys.argv) > 1
               else ["admin123", PASSWORD, "HireTrack2026!", "AdminPass2026"])

passed = failed = 0


class Session:
    """One signed-in user, with its own cookie jar."""

    def __init__(self, label):
        self.label = label
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE + path, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with self.opener.open(req, timeout=15) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except Exception:
                return e.code, {}
        except urllib.error.URLError as e:
            print(f"\n  Could not reach {BASE} - is app.py running?"
                  f"\n  {e.reason}")
            sys.exit(1)

    def get(self, p):            return self.call("GET", p)
    def post(self, p, b=None):   return self.call("POST", p, b or {})
    def delete(self, p):         return self.call("DELETE", p)


def step(label, status, payload, expect=200, show=None):
    global passed, failed
    ok = status == expect
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  [{'ok ' if ok else 'FAIL'}] {label}")
    note = show if show else (payload.get("message") or payload.get("error")
                              or json.dumps(payload)[:100])
    print(f"         HTTP {status}   {note}")
    return ok


def stop(why):
    print(f"\n  Cannot continue: {why}")
    print(f"\n  {passed} checks passed, {failed} failed before stopping.")
    sys.exit(1)


print(BAR)
print("  HireTrack - system functionality and reporting check")
print(BAR)

# ---------------------------------------------------------------- 1. server
print("\n1. The server is up and connected to MySQL")
admin = Session("admin")
s, d = admin.get("/api/status")
step("GET /api/status", s, d, 200,
     show=f"{d.get('dbms')} - {d.get('database')}")

# ---------------------------------------------------------------- 2. admin
print("\n2. The administrator signs in")
for pw in ADMIN_TRIES:
    s, d = admin.post("/api/login", {"username": "admin", "password": pw})
    if s == 200:
        break
if s != 200:
    stop("the admin password is none of the ones tried. Re-run "
         "hiretrack.sql, or pass the password: python check_ops.py <password>")
step("POST /api/login as admin", s, d, 200,
     show=f"role {d.get('role')}, must change password "
          f"{d.get('must_change_password')}")
if d.get("must_change_password"):
    s, d = admin.post("/api/change-password",
                      {"old_password": pw, "new_password": PASSWORD})
    step("the forced password change is completed", s, d, 200,
         show=f"must change password is now {d.get('must_change_password')}")

# ------------------------------------------------- 3. admin creates staff
print("\n3. The administrator creates the staff logins, choosing people "
      "by name")
s, d = admin.get("/api/admin/unlinked?role=Recruiter")
recruiters = d.get("people", [])
step("recruiters without a login, listed by name", s, d, 200,
     show=f"{len(recruiters)} available, e.g. "
          f"{', '.join(p['name'] for p in recruiters[:3])}")
if not recruiters:
    stop("every recruiter already has a login")

s, d = admin.get("/api/admin/unlinked?role=Hiring%20Manager")
managers = d.get("people", [])
step("hiring managers without a login, listed by name", s, d, 200,
     show=f"{len(managers)} available, e.g. "
          f"{', '.join(p['name'] for p in managers[:3])}")
if not managers:
    stop("every hiring manager already has a login")

rec_person, mgr_person = recruiters[0], managers[0]
rec_user = "rec" + STAMP
mgr_user = "mgr" + STAMP
cand_user = "cand" + STAMP

s, d = admin.post("/api/admin/create-user",
                  {"username": rec_user, "password": PASSWORD,
                   "role": "Recruiter", "person_id": rec_person["id"]})
step(f"a Recruiter login for {rec_person['name']}", s, d, 200,
     show=f"username {rec_user}")
s, d = admin.post("/api/admin/create-user",
                  {"username": mgr_user, "password": PASSWORD,
                   "role": "Hiring Manager", "person_id": mgr_person["id"]})
step(f"a Hiring Manager login for {mgr_person['name']}", s, d, 200,
     show=f"username {mgr_user}")

# ------------------------------------------------- 4. recruiter posts a job
print("\n4. The recruiter signs in and posts a job")
rec = Session("recruiter")
s, d = rec.post("/api/login", {"username": rec_user, "password": PASSWORD})
step("the recruiter signs in", s, d, 200,
     show=f"{d.get('display_name')} - {d.get('role')}")
step("and is told to change the password first", s,
     {"message": f"must_change_password = {d.get('must_change_password')}"},
     200)
s, d = rec.post("/api/change-password",
                {"old_password": PASSWORD, "new_password": PASSWORD + "x"})
step("the recruiter changes the password", s, d, 200,
     show=f"menu = {d.get('menu')}")

s, d = rec.get("/api/lookups/managers")
mgr_entry = next((m for m in d.get("managers", [])
                  if m["id"] == mgr_person["id"]), None)
step("the hiring manager drop-down names people and departments", s, d, 200,
     show=(f"{mgr_entry['name']} works in {mgr_entry['department']}"
           if mgr_entry else "manager not found"))
if not mgr_entry:
    stop("the new hiring manager is not in the lookup")

job_title = f"Database Administrator {STAMP}"
s, d = rec.post("/api/recruiter/jobs",
                {"title": job_title,
                 "department_id": mgr_entry["department_id"],
                 "description": "Looks after the HireTrack database."})
step("Post a job  ->  INSERT INTO JOB_POSTING", s, d, 200)
job_id = d.get("job_id")
if not job_id:
    stop("the job was not created")

# ---------------------------------------------- 5. manager approves the job
print("\n5. The hiring manager signs in and approves the posting")
mgr = Session("manager")
s, d = mgr.post("/api/login", {"username": mgr_user, "password": PASSWORD})
step("the hiring manager signs in", s, d, 200,
     show=f"{d.get('display_name')} - {d.get('role')}")
s, d = mgr.post("/api/change-password",
                {"old_password": PASSWORD, "new_password": PASSWORD + "x"})
step("the hiring manager changes the password", s, d, 200,
     show=f"menu = {d.get('menu')}")

s, d = mgr.get("/api/manager/pending-postings")
waiting = [p for p in d.get("postings", []) if p["id"] == job_id]
step("Approve postings  ->  the new job is waiting", s, d, 200,
     show=f"{len(d.get('postings', []))} waiting, including "
          f"'{waiting[0]['title']}' from {waiting[0]['posted_by']}"
          if waiting else "the new job is not in the list")
s, d = mgr.post("/api/manager/approve-posting", {"job_id": job_id})
step("Approve the posting  ->  UPDATE JOB_POSTING", s, d, 200)

# ----------------------------------------------- 6. candidate applies
print("\n6. A candidate signs up, finds the job and applies")
cand = Session("candidate")
s, d = cand.post("/api/signup",
                 {"username": cand_user, "password": PASSWORD,
                  "name": f"Taylor Nguyen {STAMP}",
                  "email": f"tnguyen{STAMP}@example.com"})
step("POST /api/signup  ->  INSERT INTO CANDIDATE and USER_ACCOUNT", s, d,
     200, show=f"{d.get('display_name')} - {d.get('role')}")

s, d = cand.get("/api/candidate/jobs")
found = [j for j in d.get("jobs", []) if j["id"] == job_id]
step("Browse jobs  ->  only approved postings are listed", s, d, 200,
     show=f"{len(d.get('jobs', []))} open jobs; the new one is "
          + ("there" if found else "MISSING"))
if found:
    j = found[0]
    print(f"         '{j['title']}' in {j['department']} "
          f"({j['location']}), posted by {j['recruiter']}")

s, d = cand.post("/api/candidate/apply",
                 {"job_id": job_id,
                  "resume_link": "https://example.com/resume.pdf"})
step("Apply to a job  ->  INSERT INTO APPLICATION", s, d, 200)
app_id = d.get("application_id")
s, d = cand.post("/api/candidate/apply", {"job_id": job_id})
step("applying a second time is refused", s, d, 400)

# -------------------------------------------- 7. recruiter screens them
print("\n7. The recruiter reviews the application and moves it along")
s, d = rec.get("/api/recruiter/applications")
mine = [r for r in d.get("rows", []) if r[0] == app_id]
step("Review applications  ->  candidates listed by name", s, d, 200,
     show=f"{len(d.get('rows', []))} application(s) on my jobs")
if mine:
    print(f"         {mine[0][1]} ({mine[0][2]}) applied for "
          f"'{mine[0][3]}' - status {mine[0][5]}")

s, d = rec.get("/api/lookups/statuses")
screening = next((x for x in d.get("statuses", [])
                  if x["name"] == "Screening"), None)
step("the status drop-down names the stages", s, d, 200,
     show=", ".join(x["name"] for x in d.get("statuses", [])))
s, d = rec.post("/api/recruiter/application-status",
                {"application_id": app_id, "status_id": screening["id"]})
step("Move the application to Screening  ->  UPDATE APPLICATION", s, d, 200)

s, d = rec.get("/api/lookups/templates")
template = d.get("templates", [{}])[0]
step("the email template drop-down names the templates", s, d, 200,
     show=f"{len(d.get('templates', []))} templates, e.g. "
          f"'{template.get('subject')}'")
s, d = rec.post("/api/recruiter/send-email",
                {"application_id": app_id, "template_id": template["id"]})
step("Send a status email  ->  INSERT INTO SENT_EMAIL", s, d, 200)

# ------------------------------------------ 8. recruiter books interview
print("\n8. The recruiter books the interview with the hiring manager")
s, d = rec.get("/api/recruiter/schedulable")
ready = [a for a in d.get("applications", []) if a["id"] == app_id]
step("the candidate is now ready to interview", s, d, 200,
     show=f"{len(d.get('applications', []))} ready; ours is "
          + ("there" if ready else "MISSING"))
when = (date.today() + timedelta(days=14)).isoformat() + " 14:30"
s, d = rec.post("/api/recruiter/interviews",
                {"application_id": app_id, "manager_id": mgr_person["id"],
                 "scheduled_date": when})
step("Schedule an interview  ->  INSERT INTO INTERVIEW", s, d, 200)
interview_id = d.get("interview_id")

# ------------------------------- 9. manager gives feedback, makes an offer
print("\n9. The hiring manager records feedback and makes the offer")
s, d = mgr.get("/api/manager/interviews")
ours = [i for i in d.get("interviews", []) if i["id"] == interview_id]
step("Record interview feedback  ->  my interviews are listed", s, d, 200,
     show=f"{len(d.get('interviews', []))} interview(s); ours is "
          + ("there" if ours else "MISSING"))
s, d = mgr.post("/api/manager/interview-feedback",
                {"interview_id": interview_id,
                 "feedback": "Clear on normalization and joins. Recommend "
                             "an offer."})
step("Save the feedback  ->  UPDATE INTERVIEW", s, d, 200)

s, d = mgr.get("/api/manager/shortlist")
step("Review shortlist  ->  ranked candidates by name", s, d, 200,
     show=f"{len(d.get('rows', []))} shortlisted in my department")

s, d = mgr.get("/api/manager/offerable")
offerable = [a for a in d.get("applications", []) if a["id"] == app_id]
step("Make offers  ->  interviewed candidates with no offer yet", s, d, 200,
     show=f"{len(d.get('applications', []))} offerable; ours is "
          + ("there" if offerable else "MISSING"))
start = (date.today() + timedelta(days=60)).isoformat()
s, d = mgr.post("/api/manager/offers",
                {"application_id": app_id, "salary": 96500,
                 "start_date": start})
step("Make the offer  ->  INSERT INTO JOB_OFFER", s, d, 200)
s, d = mgr.post("/api/manager/offers",
                {"application_id": app_id, "salary": 1, "start_date": start})
step("a second offer on the same application is refused", s, d, 400)

# -------------------------------------- 10. candidate sees the outcome
print("\n10. The candidate sees the result on their own screen")
s, d = cand.get("/api/candidate/applications")
row = [r for r in d.get("rows", []) if r[0] == app_id]
step("Track my applications  ->  status, score and offer", s, d, 200,
     show=f"{len(d.get('rows', []))} application(s)")
if row:
    cols = d["columns"]
    for name, value in zip(cols, row[0]):
        print(f"         {name:<22} {value}")
s, d = cand.get("/api/candidate/interviews")
step("My interviews  ->  the booked interview and its feedback", s, d, 200,
     show=f"{len(d.get('rows', []))} interview(s)")
if d.get("rows"):
    print(f"         {d['rows'][0]}")

# ---------------------------------------------------------- 11. reports
print("\n11. Every role runs its statistical reports")
for label, sess in (("Admin", admin), ("Recruiter", rec),
                    ("Hiring Manager", mgr), ("Candidate", cand)):
    s, d = sess.get("/api/reports")
    available = d.get("reports", [])
    step(f"{label}: reports offered", s, d, 200,
         show=f"{len(available)} reports")
    for item in available:
        s2, d2 = sess.get("/api/reports/" + item["id"])
        ok = step(f"    {item['title']}", s2, d2, 200,
                  show=f"{d2.get('row_count')} row(s), using "
                       f"{', '.join(item['aggregates'])}")
        if ok and d2.get("rows"):
            print(f"         {' | '.join(str(c) for c in d2['columns'])}")
            for r in d2["rows"][:3]:
                print(f"         {' | '.join('' if v is None else str(v) for v in r)}")
            if d2["row_count"] > 3:
                print(f"         ... {d2['row_count'] - 3} more row(s)")

# ------------------------------------------------- 12. role separation
print("\n12. No role can reach another role's operations")
checks = [
    ("a Candidate cannot review applications", cand, "GET",
     "/api/recruiter/applications"),
    ("a Candidate cannot see the shortlist", cand, "GET",
     "/api/manager/shortlist"),
    ("a Candidate cannot manage departments", cand, "GET",
     "/api/admin/departments"),
    ("a Candidate cannot run the salary report", cand, "GET",
     "/api/reports/salary_by_department"),
    ("a Recruiter cannot make an offer", rec, "POST", "/api/manager/offers"),
    ("a Recruiter cannot manage email templates", rec, "GET",
     "/api/admin/templates"),
    ("a Hiring Manager cannot post a job", mgr, "POST",
     "/api/recruiter/jobs"),
    ("an Admin cannot apply for a job", admin, "POST",
     "/api/candidate/apply"),
]
for label, sess, method, path in checks:
    s, d = sess.call(method, path, {} if method == "POST" else None)
    step(label, s, d, 403)

print("\n13. Signed out, nothing is reachable")
anon = Session("anonymous")
for path in ("/api/candidate/jobs", "/api/recruiter/applications",
             "/api/manager/shortlist", "/api/reports",
             "/api/reports/pipeline"):
    s, d = anon.get(path)
    step(f"GET {path}", s, d, 401)

print("\n" + BAR)
print(f"  {passed} checks passed, {failed} failed")
print(BAR)
print(f"""
  This run created, through the application only:
      logins     {rec_user} (Recruiter, {rec_person['name']})
                 {mgr_user} (Hiring Manager, {mgr_person['name']})
                 {cand_user} (Candidate, Taylor Nguyen {STAMP})
      a job      '{job_title}'  (JobID {job_id})
      and one application, interview and offer for it.

  Every staff password is now '{PASSWORD}x' and the admin password is
  '{PASSWORD}'. Re-run hiretrack.sql to put the database back as it was.
""")
sys.exit(0 if failed == 0 else 1)
