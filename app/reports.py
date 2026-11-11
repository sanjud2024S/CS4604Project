"""
HireTrack - reporting facility
CS 4604 Team 4 (Sanju Devakumaran, Ruthika Reddy)

Final phase, reporting requirement: statistical reports built with the
aggregate functions from the course notes. All five are used, and the
table below says which report uses which:

    COUNT   every report
    MIN     department funnel, posting performance, salary summary,
            email activity, my application summary, my interview record
    MAX     department funnel, posting performance, salary summary,
            email activity, candidate sources, my application summary,
            my interview record
    AVG     department funnel, posting performance, salary summary,
            interviewer workload, candidate sources,
            my application summary
    SUM     salary summary, my application summary

Each report is declared once, in the REPORTS table: its title, the roles
allowed to run it, the column headings, and one SELECT statement. Two
endpoints then serve all of them, so the interface needs a single report
screen rather than one screen per report.

Reports available to each kind of user:
    Admin            8      Recruiter   6
    Hiring Manager   5      Candidate   4

Only constructs from the course notes appear in the SQL:
    SELECT ... FROM ... WHERE, ORDER BY, aliases     (Chapter 4)
    INNER JOIN / LEFT OUTER JOIN ... ON              (Chapter 5)
    COUNT, MIN, MAX, AVG, SUM                        (Chapter 5)
    GROUP BY ... HAVING                              (Chapter 5)

This module is imported by app.py; it registers its routes on the app.
"""

from flask import jsonify

ALL_STAFF = ("Admin", "Recruiter", "Hiring Manager")
EVERYONE = ("Admin", "Recruiter", "Hiring Manager", "Candidate")


# =======================================================================
# The reports. `needs` names a value taken from the signed-in user and
# passed to the statement as a parameter, so a candidate's own report can
# only ever return that candidate's rows.
# =======================================================================
REPORTS = [
 {
  "id": "pipeline",
  "title": "Candidate pipeline by stage",
  "description": "How many applications are sitting at each stage of "
                 "hiring, in stage order.",
  "roles": EVERYONE,
  "aggregates": ["COUNT"],
  "columns": ["Stage", "Applications"],
  "needs": None,
  "sql": """
SELECT    s.StatusName               AS Stage,
          COUNT(a.ApplicationID)     AS Applications
FROM      HIRING_STATUS s
          LEFT OUTER JOIN APPLICATION a
          ON s.StatusID = a.StatusID
GROUP BY  s.StatusID, s.StatusName, s.StageOrder
ORDER BY  s.StageOrder""",
 },
 {
  "id": "open_jobs_by_department",
  "title": "Open postings by department",
  "description": "Where the approved, open jobs are, busiest department "
                 "first.",
  "roles": EVERYONE,
  "aggregates": ["COUNT"],
  "columns": ["Department", "Location", "Open postings"],
  "needs": None,
  "sql": """
SELECT    d.Name                     AS Department,
          d.Location                 AS Location,
          COUNT(j.JobID)             AS OpenPostings
FROM      DEPARTMENT d
          INNER JOIN JOB_POSTING j
          ON d.DepartmentID = j.DepartmentID
WHERE     j.ApprovedBy IS NOT NULL
GROUP BY  d.DepartmentID, d.Name, d.Location
ORDER BY  COUNT(j.JobID) DESC, d.Name""",
 },
 {
  "id": "department_funnel",
  "title": "Applications and scores by department",
  "description": "Application volume per department with the lowest, "
                 "average and highest candidate score.",
  "roles": ALL_STAFF,
  "aggregates": ["COUNT", "MIN", "AVG", "MAX"],
  "columns": ["Department", "Applications", "Candidates scored",
              "Lowest score", "Average score", "Highest score"],
  "needs": None,
  "sql": """
SELECT    d.Name                     AS Department,
          COUNT(a.ApplicationID)     AS Applications,
          COUNT(k.Score)             AS CandidatesScored,
          MIN(k.Score)               AS LowestScore,
          ROUND(AVG(k.Score), 2)     AS AverageScore,
          MAX(k.Score)               AS HighestScore
FROM      DEPARTMENT d
          INNER JOIN JOB_POSTING j
          ON d.DepartmentID = j.DepartmentID
          INNER JOIN APPLICATION a
          ON j.JobID = a.JobID
          LEFT OUTER JOIN CANDIDATE_RANKING k
          ON a.ApplicationID = k.ApplicationID
GROUP BY  d.DepartmentID, d.Name
HAVING    COUNT(a.ApplicationID) > 0
ORDER BY  COUNT(a.ApplicationID) DESC, d.Name""",
 },
 {
  "id": "posting_performance",
  "title": "Job posting performance",
  "description": "Every posting that has attracted at least one "
                 "applicant, with its score spread.",
  "roles": ("Admin", "Recruiter"),
  "aggregates": ["COUNT", "MIN", "AVG", "MAX"],
  "columns": ["Job title", "Department", "Posted by", "Applicants",
              "Lowest score", "Average score", "Highest score"],
  "needs": None,
  "sql": """
SELECT    j.Title                    AS JobTitle,
          d.Name                     AS Department,
          r.Name                     AS PostedBy,
          COUNT(a.ApplicationID)     AS Applicants,
          MIN(k.Score)               AS LowestScore,
          ROUND(AVG(k.Score), 2)     AS AverageScore,
          MAX(k.Score)               AS HighestScore
FROM      JOB_POSTING j
          INNER JOIN DEPARTMENT d
          ON j.DepartmentID = d.DepartmentID
          INNER JOIN RECRUITER r
          ON j.PostedBy = r.EmployeeID
          LEFT OUTER JOIN APPLICATION a
          ON j.JobID = a.JobID
          LEFT OUTER JOIN CANDIDATE_RANKING k
          ON a.ApplicationID = k.ApplicationID
GROUP BY  j.JobID, j.Title, d.Name, r.Name
HAVING    COUNT(a.ApplicationID) > 0
ORDER BY  COUNT(a.ApplicationID) DESC, j.Title""",
 },
 {
  "id": "salary_by_department",
  "title": "Offers and salary commitment by department",
  "description": "Offers made per department, the total salary "
                 "committed, and the lowest, average and highest offer.",
  "roles": ("Admin", "Hiring Manager"),
  "aggregates": ["COUNT", "SUM", "MIN", "AVG", "MAX"],
  "columns": ["Department", "Offers", "Total salary committed",
              "Lowest offer", "Average offer", "Highest offer"],
  "needs": None,
  "sql": """
SELECT    d.Name                     AS Department,
          COUNT(o.OfferID)           AS Offers,
          SUM(o.Salary)              AS TotalSalaryCommitted,
          MIN(o.Salary)              AS LowestOffer,
          ROUND(AVG(o.Salary), 2)    AS AverageOffer,
          MAX(o.Salary)              AS HighestOffer
FROM      DEPARTMENT d
          INNER JOIN JOB_POSTING j
          ON d.DepartmentID = j.DepartmentID
          INNER JOIN APPLICATION a
          ON j.JobID = a.JobID
          INNER JOIN JOB_OFFER o
          ON a.ApplicationID = o.ApplicationID
GROUP BY  d.DepartmentID, d.Name
ORDER BY  SUM(o.Salary) DESC""",
 },
 {
  "id": "interviewer_workload",
  "title": "Interview workload by hiring manager",
  "description": "Who is conducting the interviews, how much feedback "
                 "they have recorded, and the average score of the "
                 "candidates they saw.",
  "roles": ("Admin", "Hiring Manager"),
  "aggregates": ["COUNT", "AVG"],
  "columns": ["Hiring manager", "Department", "Interviews conducted",
              "Feedback recorded", "Average candidate score"],
  "needs": None,
  "sql": """
SELECT    m.Name                     AS HiringManager,
          d.Name                     AS Department,
          COUNT(i.InterviewID)       AS InterviewsConducted,
          COUNT(i.Feedback)          AS FeedbackRecorded,
          ROUND(AVG(k.Score), 2)     AS AverageCandidateScore
FROM      HIRING_MANAGER m
          INNER JOIN DEPARTMENT d
          ON m.DepartmentID = d.DepartmentID
          LEFT OUTER JOIN INTERVIEW i
          ON m.EmployeeID = i.ConductedBy
          LEFT OUTER JOIN CANDIDATE_RANKING k
          ON i.ApplicationID = k.ApplicationID
GROUP BY  m.EmployeeID, m.Name, d.Name
HAVING    COUNT(i.InterviewID) > 0
ORDER BY  COUNT(i.InterviewID) DESC, m.Name""",
 },
 {
  "id": "candidate_sources",
  "title": "Candidates by source",
  "description": "Internal, external and referral candidates compared "
                 "on volume and score.",
  "roles": ("Admin", "Recruiter"),
  "aggregates": ["COUNT", "AVG", "MAX"],
  "columns": ["Candidate type", "Candidates", "Applications",
              "Average score", "Highest score"],
  "needs": None,
  "sql": """
SELECT    c.Type                     AS CandidateType,
          COUNT(c.CandidateID)       AS Candidates,
          COUNT(a.ApplicationID)     AS Applications,
          ROUND(AVG(k.Score), 2)     AS AverageScore,
          MAX(k.Score)               AS HighestScore
FROM      CANDIDATE c
          LEFT OUTER JOIN APPLICATION a
          ON c.CandidateID = a.CandidateID
          LEFT OUTER JOIN CANDIDATE_RANKING k
          ON a.ApplicationID = k.ApplicationID
GROUP BY  c.Type
ORDER BY  COUNT(a.ApplicationID) DESC""",
 },
 {
  "id": "email_activity",
  "title": "Email template usage",
  "description": "Which status emails are actually being sent, and when "
                 "each was first and last used.",
  "roles": ("Admin", "Recruiter"),
  "aggregates": ["COUNT", "MIN", "MAX"],
  "columns": ["Template", "Times sent", "First sent", "Last sent"],
  "needs": None,
  "sql": """
SELECT    t.Subject                  AS Template,
          COUNT(e.ApplicationID)     AS TimesSent,
          MIN(e.SentDate)            AS FirstSent,
          MAX(e.SentDate)            AS LastSent
FROM      EMAIL_TEMPLATE t
          LEFT OUTER JOIN SENT_EMAIL e
          ON t.TemplateID = e.TemplateID
GROUP BY  t.TemplateID, t.Subject
HAVING    COUNT(e.ApplicationID) > 0
ORDER BY  COUNT(e.ApplicationID) DESC, t.Subject""",
 },
 {
  "id": "my_applications",
  "title": "My application summary",
  "description": "Your own totals: how many applications you have in, "
                 "how they have been scored, and any salary offered.",
  "roles": ("Candidate",),
  "aggregates": ["COUNT", "MIN", "AVG", "MAX", "SUM"],
  "columns": ["Applications submitted", "Applications scored",
              "Lowest score", "Average score", "Highest score",
              "Total salary offered"],
  "needs": "candidate_id",
  "sql": """
SELECT    COUNT(a.ApplicationID)     AS ApplicationsSubmitted,
          COUNT(k.Score)             AS ApplicationsScored,
          MIN(k.Score)               AS LowestScore,
          ROUND(AVG(k.Score), 2)     AS AverageScore,
          MAX(k.Score)               AS HighestScore,
          SUM(o.Salary)              AS TotalSalaryOffered
FROM      APPLICATION a
          LEFT OUTER JOIN CANDIDATE_RANKING k
          ON a.ApplicationID = k.ApplicationID
          LEFT OUTER JOIN JOB_OFFER o
          ON a.ApplicationID = o.ApplicationID
WHERE     a.CandidateID = %s""",
 },
 {
  "id": "my_interview_record",
  "title": "My interview record",
  "description": "How many interviews you have been scheduled for, how "
                 "many have feedback, and the dates either end.",
  "roles": ("Candidate",),
  "aggregates": ["COUNT", "MIN", "MAX"],
  "columns": ["Interviews scheduled", "Interviews with feedback",
              "First interview", "Latest interview"],
  "needs": "candidate_id",
  "sql": """
SELECT    COUNT(i.InterviewID)       AS InterviewsScheduled,
          COUNT(i.Feedback)          AS InterviewsWithFeedback,
          MIN(i.ScheduledDate)       AS FirstInterview,
          MAX(i.ScheduledDate)       AS LatestInterview
FROM      INTERVIEW i
          INNER JOIN APPLICATION a
          ON i.ApplicationID = a.ApplicationID
WHERE     a.CandidateID = %s""",
 },
]

BY_ID = {r["id"]: r for r in REPORTS}


def _j(v):
    """Dates, datetimes and Decimals are not JSON types."""
    if v is None or isinstance(v, (int, float, str)):
        return v
    return str(v)


def _shown_sql(report, params):
    """The statement with its parameter filled in, so the report screen
    can show the user exactly what was run."""
    sql = report["sql"].strip()
    for p in params:
        sql = sql.replace("%s", str(p), 1)
    return sql


def register(app, connect):
    """Attach the reporting routes to the Flask app."""

    login_required = app.login_required

    @app.get("/api/reports")
    @login_required
    def list_reports(user):
        """The reports this user is allowed to run."""
        return jsonify({"role": user["role"], "reports": [
            {"id": r["id"], "title": r["title"],
             "description": r["description"],
             "aggregates": r["aggregates"]}
            for r in REPORTS if user["role"] in r["roles"]]})

    @app.get("/api/reports/<report_id>")
    @login_required
    def run_report(user, report_id):
        """Run one report and send back its rows, its column headings and
        the SQL that produced them."""
        report = BY_ID.get(report_id)
        if not report:
            return jsonify({"error": f"There is no report '{report_id}'."}), 404
        if user["role"] not in report["roles"]:
            return jsonify({"error": "This report is not available for "
                                     f"{user['role']} users."}), 403

        params = ()
        if report["needs"]:
            value = user.get(report["needs"])
            if value is None:
                return jsonify({"error": "This report needs an account "
                                         "linked to a person."}), 400
            params = (value,)

        cx = connect(); cur = cx.cursor()
        try:
            cur.execute(report["sql"], params)
            rows = [[_j(v) for v in r] for r in cur.fetchall()]
        finally:
            cur.close(); cx.close()

        return jsonify({
            "id": report["id"],
            "title": report["title"],
            "description": report["description"],
            "aggregates": report["aggregates"],
            "columns": report["columns"],
            "rows": rows,
            "row_count": len(rows),
            "sql": _shown_sql(report, params),
        })
