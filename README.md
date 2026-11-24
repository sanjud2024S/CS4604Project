# CS4604Project - HireTrack

### Description
HireTrack is a recruitment management system with job postings, candidate applications, interview scheduling, hiring status, candidate rankings, reports, all in one centralized systems. 

### Repository Structure
database/ hiretrack.sql - 
app/ app.py, auth.py, operations.py, reports.py, index.html, check_auth.py, check_ops.py, env.example, requirements.txt
ID.txt + README.md

### Setup
1. Install MySQL 8.0 and run: mysql -u root -p < database/hiretrack.sql
2. Install python packages:
   cd app
   pip install -r requirements.txt
3. Copy env.example to .env and fill in your MySQL password and a SECRET_KEY
4. Run the server: python app.py
5. Open http://127.0.0.1:5001 in browser

### Login
For candidate accounts, the candidate creates their own account from the login page. For admin account, the username is admin with the password admin123, but the password must be changed after the first login. For recruiter and hiring manager accounts, the admin account creates those logins. 

### Checks
While the server runs, in a second separate terminal, run: python check_auth.py and python check_ops.py.
