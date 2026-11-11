# HireTrack API — what the GUI calls

CS 4604 Team 4. Backend by Sanju, interface by Ruthika.

Every path below is on the same server as the page, so `fetch` needs no
host — just `fetch("/api/candidate/jobs", {credentials: "same-origin"})`,
exactly like the existing calls in `index.html`.

**Signed out** every path returns `401`. **Wrong role** returns `403` with
`{"error": "This action is for Recruiter users."}`. **A rejected input**
returns `400` with `{"error": "..."}` already written for a person to
read, so the screen can show `error` as-is without rewording it.

No screen ever has to ask the user for an ID. Every list that feeds a
drop-down returns the **name** next to the id: show the name, post the id.

---

## Menus

`GET /api/menu` and the login response already return `menu`, an array of
strings. The items are now:

| Role | Menu items |
|---|---|
| Candidate | Browse jobs · Apply to a job · Track my applications · My interviews · **Reports** |
| Recruiter | Post a job · Review applications · Schedule interviews · Send status emails · View ranked candidates · **Reports** |
| Hiring Manager | Approve postings · Review shortlist · Record interview feedback · Make offers · **Reports** |
| Admin | Manage users · Create an admin · Manage email templates · Manage departments · **Reports** |

Two changes from before: the Candidate's *Confirm interview slots* is now
**My interviews**, and every role gained **Reports**.

---

## Table responses

Most read endpoints return the same shape, so one table renderer covers
all of them:

```json
{ "columns": ["Job title", "Status", "Score"],
  "rows":    [["Data Analyst", "Screening", 78.4],
              ["UX Researcher", "Submitted", null]] }
```

`null` means there is nothing there yet — render it as blank, not "None".

Endpoints that feed a drop-down return a named array instead
(`{"jobs": [...]}`, `{"managers": [...]}`), noted below.

---

## Lookups — the drop-downs

| Method | Path | Returns |
|---|---|---|
| GET | `/api/lookups/departments` | `departments: [{id, name, location}]` |
| GET | `/api/lookups/managers` | `managers: [{id, name, department_id, department}]` |
| GET | `/api/lookups/statuses` | `statuses: [{id, name}]` in stage order |
| GET | `/api/lookups/templates` | `templates: [{id, subject}]` |

Available to Admin, Recruiter and Hiring Manager (managers and templates:
Admin and Recruiter).

---

## Candidate

| Menu item | Method | Path | Sends | Notes |
|---|---|---|---|---|
| Browse jobs | GET | `/api/candidate/jobs` | optional `?q=word` | `jobs: [{id, title, department, location, recruiter, description, applied}]`. Only approved jobs. A job already applied to is still listed with `applied: true`, so the screen greys it out instead of hiding it. `q` filters on the title. |
| Apply to a job | POST | `/api/candidate/apply` | `{job_id, resume_link?}` | Returns `{ok, application_id, message}`. Applying twice gives `400`. |
| Track my applications | GET | `/api/candidate/applications` | — | Table: Application, Job title, Department, Submitted, Status, Score, Offer salary, Offer start date. |
| (on that screen) | DELETE | `/api/candidate/applications?application_id=N` | — | Withdraw. Returns `{ok, before, after, message}`. |
| My interviews | GET | `/api/candidate/interviews` | — | Table: Scheduled, Job title, Interviewer, Feedback. |

A candidate can only ever see and change their own rows — the signed-in
candidate's id is added to every query on the server, never sent by the
page.

---

## Recruiter

| Menu item | Method | Path | Sends | Notes |
|---|---|---|---|---|
| Post a job | GET | `/api/lookups/departments` | — | fill the department drop-down first |
| | POST | `/api/recruiter/jobs` | `{title, department_id, description?}` | `{ok, job_id, message}`. The new job is **not** visible to candidates until a hiring manager approves it — say so on the screen. |
| | GET | `/api/recruiter/jobs` | — | Table: Job, Title, Department, Applicants, Approved by. |
| Review applications | GET | `/api/recruiter/applications` | optional `?status_id=N` | Table: Application, Candidate, Email, Job title, Submitted, Status, Score. Only applications on jobs I posted. |
| | POST | `/api/recruiter/application-status` | `{application_id, status_id}` | Move to another stage. Fill the stage drop-down from `/api/lookups/statuses`. |
| Schedule interviews | GET | `/api/recruiter/schedulable` | — | `applications: [{id, candidate, job, status}]` — who is far enough along. |
| | POST | `/api/recruiter/interviews` | `{application_id, manager_id, scheduled_date}` | `scheduled_date` is `"YYYY-MM-DD HH:MM"` (an `<input type="datetime-local">` value works as-is). Also moves the application to Interviewing. |
| Send status emails | POST | `/api/recruiter/send-email` | `{application_id, template_id}` | Template drop-down from `/api/lookups/templates`. |
| | GET | `/api/recruiter/sent-emails` | — | Table: Sent, Candidate, Job title, Subject. |
| View ranked candidates | GET | `/api/recruiter/rankings` | — | Table: Job title, Rank, Candidate, Score, Status. Best score first. |

---

## Hiring Manager

| Menu item | Method | Path | Sends | Notes |
|---|---|---|---|---|
| Approve postings | GET | `/api/manager/pending-postings` | — | `postings: [{id, title, posted_by, department, description}]` — my department, not yet approved. |
| | POST | `/api/manager/approve-posting` | `{job_id}` | `{ok, message}`. |
| Review shortlist | GET | `/api/manager/shortlist` | — | Table: Job title, Rank, Candidate, Email, Score, Status. |
| Record interview feedback | GET | `/api/manager/interviews` | — | `interviews: [{id, scheduled, candidate, job, feedback}]` — mine only. `feedback` may be `null`. |
| | POST | `/api/manager/interview-feedback` | `{interview_id, feedback}` | Up to 255 characters. |
| Make offers | GET | `/api/manager/offerable` | — | `applications: [{id, candidate, job, score}]` — interviewed, no offer yet. **May legitimately be empty**; show "nobody is waiting for an offer" rather than an error. |
| | POST | `/api/manager/offers` | `{application_id, salary, start_date}` | `start_date` is `"YYYY-MM-DD"`. Also moves the application to Offer Extended. |
| | GET | `/api/manager/offers` | — | Table: Offer, Candidate, Job title, Salary, Start date, Status. |

---

## Admin

The first two menu items already work in `index.html`. The other two:

| Menu item | Method | Path | Sends | Notes |
|---|---|---|---|---|
| Manage email templates | GET | `/api/admin/templates` | — | `templates: [{id, subject, body, times_sent}]` |
| | POST | `/api/admin/templates` | `{subject, body}` | |
| | DELETE | `/api/admin/templates?template_id=N` | — | A template that has been sent **cannot** be deleted; the `400` explains why in words you can show directly. |
| Manage departments | GET | `/api/admin/departments` | — | `departments: [{id, name, location, postings}]` |
| | POST | `/api/admin/departments` | `{name, location}` | |
| | DELETE | `/api/admin/departments?department_id=N` | — | A department with postings or managers cannot be deleted; same thing, the `400` says so. |

---

## Already wired in `index.html`

These screens are done and working, so they are examples to copy from:

- **Browse jobs / Apply to a job** — `showJobs()`, `applyToJob()`
- **Track my applications** — `showMyApplications()`
- **My interviews** — `showMyInterviews()`
- **Reports** — `showReports()`, `runReport()`

`renderTable(columns, rows)` and `showTableScreen(title, path, emptyMessage)`
are shared helpers. Any endpoint in this document that returns
`{columns, rows}` is a one-line screen:

```js
function showShortlist() {
  return showTableScreen("Review shortlist",
    "/api/manager/shortlist",
    "No candidates have been ranked yet.");
}
```

Then add it to `handleMenu()`. The Recruiter and Hiring Manager screens
that still need building are the ones with a form (post a job, change a
status, schedule an interview, record feedback, make an offer) — those
follow the pattern in `showCreateUser()`.

---

## Reports — one screen covers all of them

```
GET /api/reports
  -> { role, reports: [{id, title, description, aggregates}] }
```

Only the reports this user may run. Render them as a list; the user picks
one, then:

```
GET /api/reports/<id>
  -> { id, title, description, aggregates, columns, rows, row_count, sql }
```

`columns` and `rows` go straight into the same table renderer as
everything else. `sql` is the statement that produced the rows — worth
showing in a collapsed box, since the reporting requirement is about the
SQL and it makes the demo much easier to grade.

How many each role gets: Admin 8, Recruiter 6, Hiring Manager 5,
Candidate 4. Between them they use all five aggregate functions —
`COUNT`, `MIN`, `MAX`, `AVG` and `SUM` — and each report declares which
ones it uses in `aggregates`, so the screen can show that too.

| Report id | Title | Who |
|---|---|---|
| `pipeline` | Candidate pipeline by stage | everyone |
| `open_jobs_by_department` | Open postings by department | everyone |
| `department_funnel` | Applications and scores by department | staff |
| `posting_performance` | Job posting performance | Admin, Recruiter |
| `salary_by_department` | Offers and salary commitment by department | Admin, Hiring Manager |
| `interviewer_workload` | Interview workload by hiring manager | Admin, Hiring Manager |
| `candidate_sources` | Candidates by source | Admin, Recruiter |
| `email_activity` | Email template usage | Admin, Recruiter |
| `my_applications` | My application summary | Candidate |
| `my_interview_record` | My interview record | Candidate |

---

## Checking it

With the server running (`python app.py`), `python check_ops.py` walks a
candidate through the whole workflow — an admin creates the staff logins,
a recruiter posts a job, a manager approves it, a candidate applies, gets
screened, emailed, interviewed and offered — then runs every report for
every role. 74 checks, all through these endpoints only.
