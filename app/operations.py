"""Candidate operations: browse jobs, apply, track applications.
Kept in its own file so it does not touch app.py or auth.py."""
from flask import jsonify, request
import mysql.connector
import auth


def register(app, connect):

    def candidate_id(cur, user):
        cur.execute("SELECT CandidateID FROM USER_ACCOUNT WHERE UserID = %s",
                    (user["user_id"],))
        row = cur.fetchone()
        return row[0] if row else None

    # ---- browse jobs --------------------------------------------------
    @app.get("/api/jobs")
    @app.roles_required("Candidate")
    def candidate_jobs(user):
        cx = connect(); cur = cx.cursor()
        try:
            cid = candidate_id(cur, user)
            cur.execute("""
                SELECT J.JobID, J.Title, J.Description, D.Name,
                       EXISTS (SELECT 1 FROM APPLICATION A
                               WHERE A.JobID = J.JobID AND A.CandidateID = %s)
                FROM   JOB_POSTING J
                JOIN   DEPARTMENT D ON D.DepartmentID = J.DepartmentID
                WHERE  J.ApprovedBy IS NOT NULL
                ORDER  BY J.Title""", (cid,))
            jobs = [{"job_id": r[0], "title": r[1], "description": r[2],
                     "department": r[3], "applied": bool(r[4])}
                    for r in cur.fetchall()]
            return jsonify({"jobs": jobs})
        finally:
            cur.close(); cx.close()

    # ---- apply --------------------------------------------------------
    @app.post("/api/apply")
    @app.roles_required("Candidate")
    def candidate_apply(user):
        data = request.get_json(silent=True) or {}
        try:
            job_id = int(data.get("job_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "Choose a job to apply to."}), 400
        resume = (data.get("resume_link") or "").strip() or None

        cx = connect(); cur = cx.cursor()
        try:
            cid = candidate_id(cur, user)
            cur.execute("""SELECT COUNT(*) FROM JOB_POSTING
                           WHERE JobID = %s AND ApprovedBy IS NOT NULL""",
                        (job_id,))
            if not cur.fetchone()[0]:
                return jsonify({"error": "That job is not open."}), 404
            cur.execute("""SELECT COUNT(*) FROM APPLICATION
                           WHERE CandidateID = %s AND JobID = %s""",
                        (cid, job_id))
            if cur.fetchone()[0]:
                return jsonify({"error": "You already applied to this job."}), 400

            app_id = auth._next_id(cur, "APPLICATION", "ApplicationID")
            cur.execute("""INSERT INTO APPLICATION
                             (ApplicationID, SubmissionDate, ResumeLink,
                              CandidateID, JobID, StatusID)
                           VALUES (%s, CURDATE(), %s, %s, %s, 1)""",
                        (app_id, resume, cid, job_id))
            cx.commit()
            return jsonify({"ok": True, "application_id": app_id})
        except mysql.connector.Error as e:
            cx.rollback()
            return jsonify({"error": e.msg}), 400
        finally:
            cur.close(); cx.close()

    # ---- track my applications ---------------------------------------
    @app.get("/api/my-applications")
    @app.roles_required("Candidate")
    def candidate_applications(user):
        cx = connect(); cur = cx.cursor()
        try:
            cid = candidate_id(cur, user)
            cur.execute("""
                SELECT A.ApplicationID, J.Title, D.Name, A.SubmissionDate,
                       S.StatusName
                FROM   APPLICATION A
                JOIN   JOB_POSTING J ON J.JobID = A.JobID
                JOIN   DEPARTMENT D  ON D.DepartmentID = J.DepartmentID
                JOIN   HIRING_STATUS S ON S.StatusID = A.StatusID
                WHERE  A.CandidateID = %s
                ORDER  BY A.SubmissionDate DESC, A.ApplicationID DESC""",
                (cid,))
            apps = [{"application_id": r[0], "title": r[1], "department": r[2],
                     "submitted": str(r[3]), "status": r[4]}
                    for r in cur.fetchall()]
            return jsonify({"applications": apps})
        finally:
            cur.close(); cx.close()