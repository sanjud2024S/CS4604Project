"""
HireTrack - operation-oriented task screens
CS 4604 Team 4 (Sanju Devakumaran, Ruthika Reddy)

Final phase, system functionality requirement. Every item on a role's menu
has a real operation behind it here, and each one works on the database:

  Candidate        Browse jobs              SELECT with joins
                   Apply to a job           INSERT INTO APPLICATION
                   Track my applications    SELECT with outer joins
                   Withdraw an application  DELETE FROM APPLICATION
                   My interviews            SELECT with joins

  Recruiter        Post a job               INSERT INTO JOB_POSTING
                   Review applications      SELECT + UPDATE APPLICATION
                   Schedule interviews      INSERT INTO INTERVIEW
                   Send status emails       INSERT INTO SENT_EMAIL
                   View ranked candidates   SELECT ... ORDER BY

  Hiring Manager   Approve postings         UPDATE JOB_POSTING
                   Review shortlist         SELECT with joins
                   Record interview feedback UPDATE INTERVIEW
                   Make offers              INSERT INTO JOB_OFFER + UPDATE

  Admin            Manage email templates   SELECT / INSERT / DELETE
                   Manage departments       SELECT / INSERT / DELETE

Two rules are followed throughout:

  1. Users never type an ID. Every list sends back the person's name, the
     job title or the status name next to the id, so the interface can show
     a drop-down of names and post back the id behind it.
  2. Only SQL from the course notes is used:
        SELECT ... FROM ... WHERE                       (Chapter 4)
        INSERT INTO ... VALUES / DELETE / UPDATE        (Chapter 4)
        ORDER BY, LIKE, aliases                        (Chapter 4)
        INNER JOIN / LEFT OUTER JOIN ... ON            (Chapter 5)
        nested queries with IN / NOT IN / EXISTS       (Chapter 5)
        COUNT, MAX                                     (Chapter 5)
     Dates are worked out in Python and passed as parameters, so no MySQL
     date function is needed.

This module is imported by app.py; it registers its routes on the app.
"""

from datetime import date, datetime

import mysql.connector
from flask import jsonify, request

# the stages in HIRING_STATUS, by StatusID
SUBMITTED, UNDER_REVIEW, SCREENING, INTERVIEWING, \
    OFFER_EXTENDED, HIRED, REJECTED = 1, 2, 3, 4, 5, 6, 7


# ----------------------------------------------------------------- helpers
def _j(v):
    """Dates, datetimes and Decimals are not JSON types."""
    if v is None or isinstance(v, (int, float, str)):
        return v
    return str(v)


def _rows(cur):
    return [[_j(v) for v in r] for r in cur.fetchall()]


def _table(cur, columns):
    """A list of rows plus its column headings, ready for the interface."""
    return {"columns": columns, "rows": _rows(cur)}


def _next_id(cur, table, pk):
    """MAX(pk) + 1   (Chapter 5 aggregate). The schema has no
    AUTO_INCREMENT, so new keys are worked out here."""
    cur.execute(f"SELECT MAX({pk}) FROM {table}")
    top = cur.fetchone()[0]
    try:
        return int(top) + 1
    except (TypeError, ValueError):
        return 1


def _int(data, field, label):
    """Read a required whole number out of the posted JSON."""
    raw = data.get(field)
    if raw in (None, ""):
        raise ValueError(f"Choose {label}.")
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label} is not valid.")


def _text(data, field, label, limit):
    value = (data.get(field) or "").strip()
    if not value:
        raise ValueError(f"Enter {label}.")
    if len(value) > limit:
        raise ValueError(f"{label} must be {limit} characters or fewer.")
    return value


def _my_department(cur, manager_id):
    cur.execute("""SELECT DepartmentID FROM HIRING_MANAGER
                   WHERE  EmployeeID = %s""", (manager_id,))
    row = cur.fetchone()
    return row[0] if row else None


def register(app, connect):
    """Attach the task routes to the Flask app.
    `connect` is app.py's function that opens a MySQL connection."""

    roles_required = app.roles_required

    def db(fn):
        """Open a connection, hand the cursor to fn, always close.
        A database complaint comes back as a readable message instead of
        a 500 page."""
        def run(*a, **kw):
            cx = connect(); cur = cx.cursor()
            try:
                return fn(cur, cx, *a, **kw)
            except ValueError as e:
                cx.rollback()
                return jsonify({"error": str(e)}), 400
            except mysql.connector.Error as err:
                cx.rollback()
                return jsonify({"error": err.msg, "errno": err.errno}), 400
            finally:
                cur.close(); cx.close()
        run.__name__ = fn.__name__
        return run

    # ===================================================================
    # LOOKUPS - the drop-downs, so nobody has to memorise an ID
    # ===================================================================
    @app.get("/api/lookups/departments")
    @roles_required("Admin", "Recruiter", "Hiring Manager")
    @db
    def lookup_departments(cur, cx, user):
        cur.execute("""SELECT DepartmentID, Name, Location
                       FROM   DEPARTMENT ORDER BY Name""")
        return jsonify({"departments": [
            {"id": r[0], "name": r[1], "location": r[2]}
            for r in cur.fetchall()]})

    @app.get("/api/lookups/managers")
    @roles_required("Admin", "Recruiter")
    @db
    def lookup_managers(cur, cx, user):
        """Hiring managers by name, with their department. A posting has to
        go to the department whose manager will approve it, so the
        department id comes back too."""
        cur.execute("""SELECT m.EmployeeID, m.Name, d.DepartmentID, d.Name
                       FROM   HIRING_MANAGER m
                              INNER JOIN DEPARTMENT d
                              ON m.DepartmentID = d.DepartmentID
                       ORDER BY m.Name""")
        return jsonify({"managers": [
            {"id": r[0], "name": r[1],
             "department_id": r[2], "department": r[3]}
            for r in cur.fetchall()]})

    @app.get("/api/lookups/statuses")
    @roles_required("Admin", "Recruiter", "Hiring Manager")
    @db
    def lookup_statuses(cur, cx, user):
        cur.execute("""SELECT StatusID, StatusName FROM HIRING_STATUS
                       ORDER BY StageOrder""")
        return jsonify({"statuses": [{"id": r[0], "name": r[1]}
                                     for r in cur.fetchall()]})

    @app.get("/api/lookups/templates")
    @roles_required("Admin", "Recruiter")
    @db
    def lookup_templates(cur, cx, user):
        cur.execute("""SELECT TemplateID, Subject FROM EMAIL_TEMPLATE
                       ORDER BY Subject""")
        return jsonify({"templates": [{"id": r[0], "subject": r[1]}
                                      for r in cur.fetchall()]})

    # ===================================================================
    # CANDIDATE
    # ===================================================================
    @app.get("/api/candidate/jobs")
    @roles_required("Candidate")
    @db
    def candidate_jobs(cur, cx, user):
        """Browse jobs. Only approved postings are shown. A posting the
        candidate has already applied to is still listed, but flagged, so
        the screen can grey it out instead of silently hiding it - the
        LEFT OUTER JOIN (Chapter 5) matches this candidate's application
        if there is one, and gives NULL if there is not."""
        search = (request.args.get("q") or "").strip()
        sql = """SELECT j.JobID, j.Title, d.Name, d.Location, r.Name,
                        j.Description, a.ApplicationID
                 FROM   JOB_POSTING j
                        INNER JOIN DEPARTMENT d
                        ON j.DepartmentID = d.DepartmentID
                        INNER JOIN RECRUITER r
                        ON j.PostedBy = r.EmployeeID
                        LEFT OUTER JOIN APPLICATION a
                        ON j.JobID = a.JobID
                        AND a.CandidateID = %s
                 WHERE  j.ApprovedBy IS NOT NULL"""
        params = [user["candidate_id"]]
        if search:
            sql += " AND j.Title LIKE %s"           # Chapter 4 LIKE
            params.append("%" + search + "%")
        sql += " ORDER BY j.Title"
        cur.execute(sql, tuple(params))
        return jsonify({"jobs": [
            {"id": r[0], "title": r[1], "department": r[2],
             "location": r[3], "recruiter": r[4], "description": r[5],
             "applied": r[6] is not None}
            for r in cur.fetchall()]})

    @app.post("/api/candidate/apply")
    @roles_required("Candidate")
    @db
    def candidate_apply(cur, cx, user):
        """Apply to a job - INSERT INTO APPLICATION (Chapter 4).
        The new application starts at the first stage, 'Submitted'."""
        data = request.get_json(silent=True) or {}
        job_id = _int(data, "job_id", "a job")
        resume = (data.get("resume_link") or "").strip() or None

        cur.execute("""SELECT Title FROM JOB_POSTING
                       WHERE  JobID = %s AND ApprovedBy IS NOT NULL""",
                    (job_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("That job is not open for applications.")
        title = row[0]

        # UNIQUE (CandidateID, JobID) would catch this too; checking first
        # gives a message that makes sense to the user
        cur.execute("""SELECT COUNT(*) FROM APPLICATION
                       WHERE  CandidateID = %s AND JobID = %s""",
                    (user["candidate_id"], job_id))
        if cur.fetchone()[0]:
            raise ValueError("You have already applied to this job.")

        app_id = _next_id(cur, "APPLICATION", "ApplicationID")
        cur.execute("""INSERT INTO APPLICATION
                         (ApplicationID, SubmissionDate, ResumeLink,
                          CandidateID, JobID, StatusID)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (app_id, date.today().isoformat(), resume,
                     user["candidate_id"], job_id, SUBMITTED))
        cx.commit()
        return jsonify({"ok": True, "application_id": app_id,
                        "message": f"Your application for {title} was "
                                   f"submitted."})

    @app.get("/api/candidate/applications")
    @roles_required("Candidate")
    @db
    def candidate_applications(cur, cx, user):
        """Track my applications. LEFT OUTER JOIN (Chapter 5) so an
        application with no score and no offer yet still appears."""
        cur.execute("""SELECT a.ApplicationID, j.Title, d.Name,
                              a.SubmissionDate, s.StatusName,
                              k.Score, o.Salary, o.StartDate
                       FROM   APPLICATION a
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                              INNER JOIN DEPARTMENT d
                              ON j.DepartmentID = d.DepartmentID
                              INNER JOIN HIRING_STATUS s
                              ON a.StatusID = s.StatusID
                              LEFT OUTER JOIN CANDIDATE_RANKING k
                              ON a.ApplicationID = k.ApplicationID
                              LEFT OUTER JOIN JOB_OFFER o
                              ON a.ApplicationID = o.ApplicationID
                       WHERE  a.CandidateID = %s
                       ORDER BY a.SubmissionDate DESC""",
                    (user["candidate_id"],))
        return jsonify(_table(cur, ["Application", "Job title", "Department",
                                    "Submitted", "Status", "Score",
                                    "Offer salary", "Offer start date"]))

    @app.delete("/api/candidate/applications")
    @roles_required("Candidate")
    @db
    def candidate_withdraw(cur, cx, user):
        """Withdraw an application - DELETE FROM APPLICATION (Chapter 4).
        The WHERE clause carries the candidate's own id as well as the
        application id, so one candidate cannot delete another's row."""
        app_id = _int(request.args.to_dict(), "application_id",
                      "an application")
        cur.execute("""SELECT COUNT(*) FROM APPLICATION
                       WHERE  ApplicationID = %s AND CandidateID = %s""",
                    (app_id, user["candidate_id"]))
        if not cur.fetchone()[0]:
            raise ValueError("That application is not yours.")

        cur.execute("SELECT COUNT(*) FROM APPLICATION WHERE CandidateID = %s",
                    (user["candidate_id"],))
        before = cur.fetchone()[0]
        cur.execute("""DELETE FROM APPLICATION
                       WHERE  ApplicationID = %s AND CandidateID = %s""",
                    (app_id, user["candidate_id"]))
        cx.commit()
        cur.execute("SELECT COUNT(*) FROM APPLICATION WHERE CandidateID = %s",
                    (user["candidate_id"],))
        after = cur.fetchone()[0]
        return jsonify({"ok": True, "before": before, "after": after,
                        "message": "The application was withdrawn."})

    @app.get("/api/candidate/interviews")
    @roles_required("Candidate")
    @db
    def candidate_interviews(cur, cx, user):
        """My interviews, with the job and the interviewer by name."""
        cur.execute("""SELECT i.ScheduledDate, j.Title, m.Name, i.Feedback
                       FROM   INTERVIEW i
                              INNER JOIN APPLICATION a
                              ON i.ApplicationID = a.ApplicationID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                              INNER JOIN HIRING_MANAGER m
                              ON i.ConductedBy = m.EmployeeID
                       WHERE  a.CandidateID = %s
                       ORDER BY i.ScheduledDate""",
                    (user["candidate_id"],))
        return jsonify(_table(cur, ["Scheduled", "Job title",
                                    "Interviewer", "Feedback"]))

    # ===================================================================
    # RECRUITER
    # ===================================================================
    @app.post("/api/recruiter/jobs")
    @roles_required("Recruiter")
    @db
    def recruiter_post_job(cur, cx, user):
        """Post a job - INSERT INTO JOB_POSTING (Chapter 4).
        ApprovedBy is left NULL: a hiring manager approves it afterwards."""
        data = request.get_json(silent=True) or {}
        title = _text(data, "title", "a job title", 120)
        dept  = _int(data, "department_id", "a department")
        desc  = (data.get("description") or "").strip() or None
        if desc and len(desc) > 500:
            raise ValueError("The description must be 500 characters or fewer.")

        job_id = _next_id(cur, "JOB_POSTING", "JobID")
        cur.execute("""INSERT INTO JOB_POSTING
                         (JobID, Title, Description, DepartmentID, PostedBy)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (job_id, title, desc, dept, user["recruiter_id"]))
        cx.commit()
        return jsonify({"ok": True, "job_id": job_id,
                        "message": f"'{title}' was posted and is waiting for "
                                   f"a hiring manager to approve it."})

    @app.get("/api/recruiter/jobs")
    @roles_required("Recruiter")
    @db
    def recruiter_my_jobs(cur, cx, user):
        """My postings, with how many have applied to each.
        COUNT(*) with GROUP BY (Chapter 5); LEFT OUTER JOIN keeps a
        posting with no applicants in the list."""
        cur.execute("""SELECT j.JobID, j.Title, d.Name,
                              COUNT(a.ApplicationID), m.Name
                       FROM   JOB_POSTING j
                              INNER JOIN DEPARTMENT d
                              ON j.DepartmentID = d.DepartmentID
                              LEFT OUTER JOIN APPLICATION a
                              ON j.JobID = a.JobID
                              LEFT OUTER JOIN HIRING_MANAGER m
                              ON j.ApprovedBy = m.EmployeeID
                       WHERE  j.PostedBy = %s
                       GROUP BY j.JobID, j.Title, d.Name, m.Name
                       ORDER BY j.Title""",
                    (user["recruiter_id"],))
        return jsonify(_table(cur, ["Job", "Title", "Department",
                                    "Applicants", "Approved by"]))

    @app.get("/api/recruiter/applications")
    @roles_required("Recruiter")
    @db
    def recruiter_applications(cur, cx, user):
        """Review applications on the jobs I posted. Candidates appear by
        name, and the list can be narrowed to one stage."""
        status = request.args.get("status_id")
        sql = """SELECT a.ApplicationID, c.Name, c.Email, j.Title,
                        a.SubmissionDate, s.StatusName, k.Score
                 FROM   APPLICATION a
                        INNER JOIN CANDIDATE c
                        ON a.CandidateID = c.CandidateID
                        INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                        INNER JOIN HIRING_STATUS s
                        ON a.StatusID = s.StatusID
                        LEFT OUTER JOIN CANDIDATE_RANKING k
                        ON a.ApplicationID = k.ApplicationID
                 WHERE  j.PostedBy = %s"""
        params = [user["recruiter_id"]]
        if status not in (None, "", "all"):
            sql += " AND a.StatusID = %s"
            params.append(status)
        sql += " ORDER BY a.SubmissionDate DESC"
        cur.execute(sql, tuple(params))
        return jsonify(_table(cur, ["Application", "Candidate", "Email",
                                    "Job title", "Submitted", "Status",
                                    "Score"]))

    @app.post("/api/recruiter/application-status")
    @roles_required("Recruiter")
    @db
    def recruiter_set_status(cur, cx, user):
        """Move an application to another stage - UPDATE (Chapter 4)."""
        data = request.get_json(silent=True) or {}
        app_id = _int(data, "application_id", "an application")
        status = _int(data, "status_id", "a status")

        cur.execute("""SELECT c.Name, s.StatusName
                       FROM   APPLICATION a
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN HIRING_STATUS s
                              ON a.StatusID = s.StatusID
                       WHERE  a.ApplicationID = %s AND j.PostedBy = %s""",
                    (app_id, user["recruiter_id"]))
        row = cur.fetchone()
        if not row:
            raise ValueError("That application is not on one of your jobs.")
        name, was = row

        cur.execute("SELECT StatusName FROM HIRING_STATUS WHERE StatusID = %s",
                    (status,))
        new = cur.fetchone()
        if not new:
            raise ValueError("That is not a valid status.")

        cur.execute("""UPDATE APPLICATION SET StatusID = %s
                       WHERE  ApplicationID = %s""", (status, app_id))
        cx.commit()
        return jsonify({"ok": True,
                        "message": f"{name} moved from {was} to {new[0]}."})

    @app.get("/api/recruiter/schedulable")
    @roles_required("Recruiter")
    @db
    def recruiter_schedulable(cur, cx, user):
        """Applications on my jobs that are far enough along to interview."""
        cur.execute("""SELECT a.ApplicationID, c.Name, j.Title, s.StatusName
                       FROM   APPLICATION a
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                              INNER JOIN HIRING_STATUS s
                              ON a.StatusID = s.StatusID
                       WHERE  j.PostedBy = %s
                         AND  a.StatusID IN (%s, %s, %s)
                       ORDER BY c.Name""",
                    (user["recruiter_id"], SCREENING, INTERVIEWING,
                     UNDER_REVIEW))
        return jsonify({"applications": [
            {"id": r[0], "candidate": r[1], "job": r[2], "status": r[3]}
            for r in cur.fetchall()]})

    @app.post("/api/recruiter/interviews")
    @roles_required("Recruiter")
    @db
    def recruiter_schedule_interview(cur, cx, user):
        """Schedule an interview - INSERT INTO INTERVIEW (Chapter 4).
        The application also moves to the 'Interviewing' stage."""
        data = request.get_json(silent=True) or {}
        app_id  = _int(data, "application_id", "an application")
        manager = _int(data, "manager_id", "a hiring manager")
        when    = (data.get("scheduled_date") or "").strip()
        if not when:
            raise ValueError("Enter the date and time of the interview.")
        try:
            # accept "2026-11-20 14:00" or "2026-11-20T14:00" from the form
            stamp = datetime.fromisoformat(when.replace(" ", "T"))
        except ValueError:
            raise ValueError("Use the format YYYY-MM-DD HH:MM for the date.")

        cur.execute("""SELECT c.Name, j.Title
                       FROM   APPLICATION a
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                       WHERE  a.ApplicationID = %s AND j.PostedBy = %s""",
                    (app_id, user["recruiter_id"]))
        row = cur.fetchone()
        if not row:
            raise ValueError("That application is not on one of your jobs.")

        interview_id = _next_id(cur, "INTERVIEW", "InterviewID")
        cur.execute("""INSERT INTO INTERVIEW
                         (InterviewID, ScheduledDate, ApplicationID,
                          ConductedBy)
                       VALUES (%s, %s, %s, %s)""",
                    (interview_id, stamp.strftime("%Y-%m-%d %H:%M:%S"),
                     app_id, manager))
        cur.execute("""UPDATE APPLICATION SET StatusID = %s
                       WHERE  ApplicationID = %s""", (INTERVIEWING, app_id))
        cx.commit()
        return jsonify({"ok": True, "interview_id": interview_id,
                        "message": f"Interview booked for {row[0]} "
                                   f"({row[1]}) on "
                                   f"{stamp.strftime('%Y-%m-%d %H:%M')}."})

    @app.post("/api/recruiter/send-email")
    @roles_required("Recruiter")
    @db
    def recruiter_send_email(cur, cx, user):
        """Send a status email - INSERT INTO SENT_EMAIL (Chapter 4).
        SENT_EMAIL is the junction table for the M:N relationship between
        applications and templates, so the send is recorded as a row."""
        data = request.get_json(silent=True) or {}
        app_id   = _int(data, "application_id", "an application")
        template = _int(data, "template_id", "an email template")

        cur.execute("""SELECT c.Name, c.Email
                       FROM   APPLICATION a
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                       WHERE  a.ApplicationID = %s AND j.PostedBy = %s""",
                    (app_id, user["recruiter_id"]))
        who = cur.fetchone()
        if not who:
            raise ValueError("That application is not on one of your jobs.")

        cur.execute("SELECT Subject FROM EMAIL_TEMPLATE WHERE TemplateID = %s",
                    (template,))
        subject = cur.fetchone()
        if not subject:
            raise ValueError("That email template does not exist.")

        cur.execute("""INSERT INTO SENT_EMAIL
                         (ApplicationID, TemplateID, SentDate)
                       VALUES (%s, %s, %s)""",
                    (app_id, template,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        cx.commit()
        return jsonify({"ok": True,
                        "message": f"'{subject[0]}' was sent to {who[0]} "
                                   f"at {who[1]}."})

    @app.get("/api/recruiter/sent-emails")
    @roles_required("Recruiter")
    @db
    def recruiter_sent_emails(cur, cx, user):
        """What has already been sent, newest first."""
        cur.execute("""SELECT e.SentDate, c.Name, j.Title, t.Subject
                       FROM   SENT_EMAIL e
                              INNER JOIN APPLICATION a
                              ON e.ApplicationID = a.ApplicationID
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                              INNER JOIN EMAIL_TEMPLATE t
                              ON e.TemplateID = t.TemplateID
                       WHERE  j.PostedBy = %s
                       ORDER BY e.SentDate DESC""",
                    (user["recruiter_id"],))
        return jsonify(_table(cur, ["Sent", "Candidate", "Job title",
                                    "Subject"]))

    @app.get("/api/recruiter/rankings")
    @roles_required("Recruiter")
    @db
    def recruiter_rankings(cur, cx, user):
        """View ranked candidates for the jobs I posted, best score first."""
        cur.execute("""SELECT j.Title, k.RankPosition, c.Name, k.Score,
                              s.StatusName
                       FROM   CANDIDATE_RANKING k
                              INNER JOIN APPLICATION a
                              ON k.ApplicationID = a.ApplicationID
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                              INNER JOIN HIRING_STATUS s
                              ON a.StatusID = s.StatusID
                       WHERE  j.PostedBy = %s
                       ORDER BY j.Title, k.Score DESC""",
                    (user["recruiter_id"],))
        return jsonify(_table(cur, ["Job title", "Rank", "Candidate",
                                    "Score", "Status"]))

    # ===================================================================
    # HIRING MANAGER
    # ===================================================================
    @app.get("/api/manager/pending-postings")
    @roles_required("Hiring Manager")
    @db
    def manager_pending(cur, cx, user):
        """Postings in my department that nobody has approved yet."""
        dept = _my_department(cur, user["manager_id"])
        cur.execute("""SELECT j.JobID, j.Title, r.Name, d.Name, j.Description
                       FROM   JOB_POSTING j
                              INNER JOIN RECRUITER r
                              ON j.PostedBy = r.EmployeeID
                              INNER JOIN DEPARTMENT d
                              ON j.DepartmentID = d.DepartmentID
                       WHERE  j.DepartmentID = %s AND j.ApprovedBy IS NULL
                       ORDER BY j.Title""", (dept,))
        return jsonify({"postings": [
            {"id": r[0], "title": r[1], "posted_by": r[2],
             "department": r[3], "description": r[4]}
            for r in cur.fetchall()]})

    @app.post("/api/manager/approve-posting")
    @roles_required("Hiring Manager")
    @db
    def manager_approve(cur, cx, user):
        """Approve a posting - UPDATE JOB_POSTING (Chapter 4). Once
        ApprovedBy is set, candidates can see and apply to the job."""
        data = request.get_json(silent=True) or {}
        job_id = _int(data, "job_id", "a posting")
        dept = _my_department(cur, user["manager_id"])

        cur.execute("""SELECT Title FROM JOB_POSTING
                       WHERE  JobID = %s AND DepartmentID = %s
                         AND  ApprovedBy IS NULL""", (job_id, dept))
        row = cur.fetchone()
        if not row:
            raise ValueError("That posting is not waiting for your approval.")

        cur.execute("""UPDATE JOB_POSTING SET ApprovedBy = %s
                       WHERE  JobID = %s""", (user["manager_id"], job_id))
        cx.commit()
        return jsonify({"ok": True,
                        "message": f"'{row[0]}' is approved and open for "
                                   f"applications."})

    @app.get("/api/manager/shortlist")
    @roles_required("Hiring Manager")
    @db
    def manager_shortlist(cur, cx, user):
        """Review shortlist: the ranked candidates for my department's jobs."""
        dept = _my_department(cur, user["manager_id"])
        cur.execute("""SELECT j.Title, k.RankPosition, c.Name, c.Email,
                              k.Score, s.StatusName
                       FROM   CANDIDATE_RANKING k
                              INNER JOIN APPLICATION a
                              ON k.ApplicationID = a.ApplicationID
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                              INNER JOIN HIRING_STATUS s
                              ON a.StatusID = s.StatusID
                       WHERE  j.DepartmentID = %s
                       ORDER BY j.Title, k.Score DESC""", (dept,))
        return jsonify(_table(cur, ["Job title", "Rank", "Candidate",
                                    "Email", "Score", "Status"]))

    @app.get("/api/manager/interviews")
    @roles_required("Hiring Manager")
    @db
    def manager_interviews(cur, cx, user):
        """The interviews I am down to conduct, so feedback can be added."""
        cur.execute("""SELECT i.InterviewID, i.ScheduledDate, c.Name,
                              j.Title, i.Feedback
                       FROM   INTERVIEW i
                              INNER JOIN APPLICATION a
                              ON i.ApplicationID = a.ApplicationID
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                       WHERE  i.ConductedBy = %s
                       ORDER BY i.ScheduledDate DESC""",
                    (user["manager_id"],))
        return jsonify({"interviews": [
            {"id": r[0], "scheduled": _j(r[1]), "candidate": r[2],
             "job": r[3], "feedback": r[4]} for r in cur.fetchall()]})

    @app.post("/api/manager/interview-feedback")
    @roles_required("Hiring Manager")
    @db
    def manager_feedback(cur, cx, user):
        """Record interview feedback - UPDATE INTERVIEW (Chapter 4)."""
        data = request.get_json(silent=True) or {}
        interview_id = _int(data, "interview_id", "an interview")
        feedback = _text(data, "feedback", "your feedback", 255)

        cur.execute("""SELECT c.Name
                       FROM   INTERVIEW i
                              INNER JOIN APPLICATION a
                              ON i.ApplicationID = a.ApplicationID
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                       WHERE  i.InterviewID = %s AND i.ConductedBy = %s""",
                    (interview_id, user["manager_id"]))
        row = cur.fetchone()
        if not row:
            raise ValueError("That interview is not one of yours.")

        cur.execute("""UPDATE INTERVIEW SET Feedback = %s
                       WHERE  InterviewID = %s""", (feedback, interview_id))
        cx.commit()
        return jsonify({"ok": True,
                        "message": f"Feedback saved for {row[0]}."})

    @app.get("/api/manager/offerable")
    @roles_required("Hiring Manager")
    @db
    def manager_offerable(cur, cx, user):
        """Candidates an offer can be made to: they have been interviewed
        for one of my department's jobs and have no offer yet. EXISTS
        finds the ones with an interview and NOT IN removes the ones
        already offered (both Chapter 5 nested queries)."""
        dept = _my_department(cur, user["manager_id"])
        cur.execute("""SELECT a.ApplicationID, c.Name, j.Title, k.Score
                       FROM   APPLICATION a
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                              LEFT OUTER JOIN CANDIDATE_RANKING k
                              ON a.ApplicationID = k.ApplicationID
                       WHERE  j.DepartmentID = %s
                         AND  EXISTS (SELECT * FROM INTERVIEW i
                                      WHERE  i.ApplicationID =
                                             a.ApplicationID)
                         AND  a.ApplicationID NOT IN
                                (SELECT ApplicationID FROM JOB_OFFER)
                       ORDER BY c.Name""",
                    (dept,))
        return jsonify({"applications": [
            {"id": r[0], "candidate": r[1], "job": r[2], "score": _j(r[3])}
            for r in cur.fetchall()]})

    @app.post("/api/manager/offers")
    @roles_required("Hiring Manager")
    @db
    def manager_make_offer(cur, cx, user):
        """Make an offer - INSERT INTO JOB_OFFER (Chapter 4), and move the
        application to the 'Offer Extended' stage."""
        data = request.get_json(silent=True) or {}
        app_id = _int(data, "application_id", "a candidate")
        start  = (data.get("start_date") or "").strip()
        try:
            salary = float(data.get("salary"))
        except (TypeError, ValueError):
            raise ValueError("Enter the salary as a number.")
        if salary <= 0:
            raise ValueError("The salary must be greater than zero.")
        try:
            start_date = date.fromisoformat(start)
        except ValueError:
            raise ValueError("Use the format YYYY-MM-DD for the start date.")

        dept = _my_department(cur, user["manager_id"])
        cur.execute("""SELECT c.Name, j.Title
                       FROM   APPLICATION a
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                       WHERE  a.ApplicationID = %s AND j.DepartmentID = %s""",
                    (app_id, dept))
        row = cur.fetchone()
        if not row:
            raise ValueError("That application is not in your department.")

        # UNIQUE (ApplicationID) on JOB_OFFER allows only one offer per
        # application; this gives a readable message instead of error 1062
        cur.execute("SELECT COUNT(*) FROM JOB_OFFER WHERE ApplicationID = %s",
                    (app_id,))
        if cur.fetchone()[0]:
            raise ValueError("This candidate already has an offer.")

        offer_id = _next_id(cur, "JOB_OFFER", "OfferID")
        cur.execute("""INSERT INTO JOB_OFFER
                         (OfferID, Salary, StartDate, ApplicationID)
                       VALUES (%s, %s, %s, %s)""",
                    (offer_id, salary, start_date.isoformat(), app_id))
        cur.execute("""UPDATE APPLICATION SET StatusID = %s
                       WHERE  ApplicationID = %s""",
                    (OFFER_EXTENDED, app_id))
        cx.commit()
        return jsonify({"ok": True, "offer_id": offer_id,
                        "message": f"Offer of {salary:,.2f} made to {row[0]} "
                                   f"for {row[1]}, starting {start}."})

    @app.get("/api/manager/offers")
    @roles_required("Hiring Manager")
    @db
    def manager_offers(cur, cx, user):
        """The offers already made in my department."""
        dept = _my_department(cur, user["manager_id"])
        cur.execute("""SELECT o.OfferID, c.Name, j.Title, o.Salary,
                              o.StartDate, s.StatusName
                       FROM   JOB_OFFER o
                              INNER JOIN APPLICATION a
                              ON o.ApplicationID = a.ApplicationID
                              INNER JOIN CANDIDATE c
                              ON a.CandidateID = c.CandidateID
                              INNER JOIN JOB_POSTING j ON a.JobID = j.JobID
                              INNER JOIN HIRING_STATUS s
                              ON a.StatusID = s.StatusID
                       WHERE  j.DepartmentID = %s
                       ORDER BY o.StartDate DESC""", (dept,))
        return jsonify(_table(cur, ["Offer", "Candidate", "Job title",
                                    "Salary", "Start date", "Status"]))

    # ===================================================================
    # ADMIN - reference data behind the remaining two menu items
    # ===================================================================
    @app.get("/api/admin/templates")
    @roles_required("Admin")
    @db
    def admin_templates(cur, cx, user):
        """Email templates, with how many times each has been used.
        COUNT(*) with GROUP BY (Chapter 5)."""
        cur.execute("""SELECT t.TemplateID, t.Subject, t.Body,
                              COUNT(e.ApplicationID)
                       FROM   EMAIL_TEMPLATE t
                              LEFT OUTER JOIN SENT_EMAIL e
                              ON t.TemplateID = e.TemplateID
                       GROUP BY t.TemplateID, t.Subject, t.Body
                       ORDER BY t.Subject""")
        return jsonify({"templates": [
            {"id": r[0], "subject": r[1], "body": r[2], "times_sent": r[3]}
            for r in cur.fetchall()]})

    @app.post("/api/admin/templates")
    @roles_required("Admin")
    @db
    def admin_add_template(cur, cx, user):
        data = request.get_json(silent=True) or {}
        subject = _text(data, "subject", "a subject line", 200)
        body    = _text(data, "body", "the message body", 500)
        tid = _next_id(cur, "EMAIL_TEMPLATE", "TemplateID")
        cur.execute("""INSERT INTO EMAIL_TEMPLATE (TemplateID, Subject, Body)
                       VALUES (%s, %s, %s)""", (tid, subject, body))
        cx.commit()
        return jsonify({"ok": True, "template_id": tid,
                        "message": f"Template '{subject}' was added."})

    @app.delete("/api/admin/templates")
    @roles_required("Admin")
    @db
    def admin_delete_template(cur, cx, user):
        """A template that has already been sent cannot be deleted: the
        foreign key on SENT_EMAIL is ON DELETE RESTRICT, so this checks
        first and explains why."""
        tid = _int(request.args.to_dict(), "template_id", "a template")
        cur.execute("SELECT COUNT(*) FROM SENT_EMAIL WHERE TemplateID = %s",
                    (tid,))
        used = cur.fetchone()[0]
        if used:
            raise ValueError(f"This template has been sent {used} time(s), "
                             f"so it cannot be deleted.")
        cur.execute("SELECT COUNT(*) FROM EMAIL_TEMPLATE")
        before = cur.fetchone()[0]
        cur.execute("DELETE FROM EMAIL_TEMPLATE WHERE TemplateID = %s", (tid,))
        cx.commit()
        cur.execute("SELECT COUNT(*) FROM EMAIL_TEMPLATE")
        return jsonify({"ok": True, "before": before,
                        "after": cur.fetchone()[0],
                        "message": "The template was deleted."})

    @app.get("/api/admin/departments")
    @roles_required("Admin")
    @db
    def admin_departments(cur, cx, user):
        """Departments, with their manager and posting counts."""
        cur.execute("""SELECT d.DepartmentID, d.Name, d.Location,
                              COUNT(j.JobID)
                       FROM   DEPARTMENT d
                              LEFT OUTER JOIN JOB_POSTING j
                              ON d.DepartmentID = j.DepartmentID
                       GROUP BY d.DepartmentID, d.Name, d.Location
                       ORDER BY d.Name""")
        return jsonify({"departments": [
            {"id": r[0], "name": r[1], "location": r[2], "postings": r[3]}
            for r in cur.fetchall()]})

    @app.post("/api/admin/departments")
    @roles_required("Admin")
    @db
    def admin_add_department(cur, cx, user):
        data = request.get_json(silent=True) or {}
        name     = _text(data, "name", "a department name", 100)
        location = _text(data, "location", "a location", 100)
        did = _next_id(cur, "DEPARTMENT", "DepartmentID")
        cur.execute("""INSERT INTO DEPARTMENT (DepartmentID, Name, Location)
                       VALUES (%s, %s, %s)""", (did, name, location))
        cx.commit()
        return jsonify({"ok": True, "department_id": did,
                        "message": f"{name} was added."})

    @app.delete("/api/admin/departments")
    @roles_required("Admin")
    @db
    def admin_delete_department(cur, cx, user):
        """Both JOB_POSTING and HIRING_MANAGER reference DEPARTMENT with
        ON DELETE RESTRICT, so a department still in use is kept."""
        did = _int(request.args.to_dict(), "department_id", "a department")
        cur.execute("SELECT COUNT(*) FROM JOB_POSTING WHERE DepartmentID = %s",
                    (did,))
        jobs = cur.fetchone()[0]
        cur.execute("""SELECT COUNT(*) FROM HIRING_MANAGER
                       WHERE  DepartmentID = %s""", (did,))
        managers = cur.fetchone()[0]
        if jobs or managers:
            raise ValueError(f"This department has {jobs} posting(s) and "
                             f"{managers} manager(s), so it cannot be "
                             f"deleted.")
        cur.execute("SELECT COUNT(*) FROM DEPARTMENT")
        before = cur.fetchone()[0]
        cur.execute("DELETE FROM DEPARTMENT WHERE DepartmentID = %s", (did,))
        cx.commit()
        cur.execute("SELECT COUNT(*) FROM DEPARTMENT")
        return jsonify({"ok": True, "before": before,
                        "after": cur.fetchone()[0],
                        "message": "The department was deleted."})
