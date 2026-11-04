-- =====================================================================
-- HireTrack: An Integrated Recruitment Database System
-- CS 4604 - Team 4 (Sanju Devakumaran, Ruthika Reddy)
-- Phase 1: Schema creation and sample data
-- DBMS: MySQL 8.0
--
-- 14 relations, 14 primary keys, 17 foreign keys.
-- Uses only Chapter 4 features: CREATE TABLE, data types, NOT NULL,
-- DEFAULT, UNIQUE, CHECK, PRIMARY KEY, FOREIGN KEY with referential
-- integrity options, INSERT, and SELECT-FROM-WHERE.
-- =====================================================================

DROP DATABASE IF EXISTS hiretrack;
CREATE DATABASE hiretrack;
USE hiretrack;

-- =====================================================================
-- SECTION 1: TABLE DEFINITIONS
-- Tables are created parent-first so every FOREIGN KEY refers to a
-- table that already exists.
-- =====================================================================

CREATE TABLE DEPARTMENT (
    DepartmentID    INT             NOT NULL,
    Name            VARCHAR(100)    NOT NULL,
    Location        VARCHAR(100)    NOT NULL,
    PRIMARY KEY (DepartmentID),
    UNIQUE (Name) );

CREATE TABLE RECRUITER (
    EmployeeID      INT             NOT NULL,
    Name            VARCHAR(100)    NOT NULL,
    Email           VARCHAR(120)    NOT NULL,
    PRIMARY KEY (EmployeeID),
    UNIQUE (Email) );

CREATE TABLE CANDIDATE (
    CandidateID     INT             NOT NULL,
    Name            VARCHAR(100)    NOT NULL,
    Email           VARCHAR(120)    NOT NULL,
    Type            VARCHAR(20)     NOT NULL DEFAULT 'External'
                    CHECK (Type IN ('Internal','External','Referral')),
    PRIMARY KEY (CandidateID),
    UNIQUE (Email) );

CREATE TABLE HIRING_STATUS (
    StatusID        INT             NOT NULL,
    StatusName      VARCHAR(40)     NOT NULL,
    StageOrder      INT             NOT NULL CHECK (StageOrder > 0),
    PRIMARY KEY (StatusID),
    UNIQUE (StatusName),
    UNIQUE (StageOrder) );

CREATE TABLE EMAIL_TEMPLATE (
    TemplateID      INT             NOT NULL,
    Subject         VARCHAR(200)    NOT NULL,
    Body            VARCHAR(500)    NOT NULL,
    PRIMARY KEY (TemplateID) );

-- DepartmentID maps the "Works In" relationship (Department 1 : N Hiring Manager)
CREATE TABLE HIRING_MANAGER (
    EmployeeID      INT             NOT NULL,
    Name            VARCHAR(100)    NOT NULL,
    Email           VARCHAR(120)    NOT NULL,
    DepartmentID    INT             NOT NULL,
    PRIMARY KEY (EmployeeID),
    UNIQUE (Email),
    FOREIGN KEY (DepartmentID) REFERENCES DEPARTMENT (DepartmentID)
        ON DELETE RESTRICT ON UPDATE CASCADE );

CREATE TABLE ANALYTICS_REPORT (
    ReportID        INT             NOT NULL,
    ReportType      VARCHAR(60)     NOT NULL,
    GeneratedDate   DATE            NOT NULL,
    GeneratedBy     INT             NOT NULL,
    PRIMARY KEY (ReportID),
    FOREIGN KEY (GeneratedBy) REFERENCES RECRUITER (EmployeeID)
        ON DELETE RESTRICT ON UPDATE CASCADE );

CREATE TABLE JOB_POSTING (
    JobID           INT             NOT NULL,
    Title           VARCHAR(120)    NOT NULL,
    Description     VARCHAR(500),
    DepartmentID    INT             NOT NULL,
    PostedBy        INT             NOT NULL,
    ApprovedBy      INT,
    PRIMARY KEY (JobID),
    FOREIGN KEY (DepartmentID) REFERENCES DEPARTMENT (DepartmentID)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (PostedBy) REFERENCES RECRUITER (EmployeeID)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (ApprovedBy) REFERENCES HIRING_MANAGER (EmployeeID)
        ON DELETE SET NULL ON UPDATE CASCADE );

CREATE TABLE APPLICATION (
    ApplicationID   INT             NOT NULL,
    SubmissionDate  DATE            NOT NULL,
    ResumeLink      VARCHAR(255),
    CandidateID     INT             NOT NULL,
    JobID           INT             NOT NULL,
    StatusID        INT             NOT NULL,
    PRIMARY KEY (ApplicationID),
    UNIQUE (CandidateID, JobID),
    FOREIGN KEY (CandidateID) REFERENCES CANDIDATE (CandidateID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (JobID) REFERENCES JOB_POSTING (JobID)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (StatusID) REFERENCES HIRING_STATUS (StatusID)
        ON DELETE RESTRICT ON UPDATE CASCADE );

-- ApplicationID maps "Schedules", ConductedBy maps "Conducts"
CREATE TABLE INTERVIEW (
    InterviewID     INT             NOT NULL,
    ScheduledDate   DATETIME        NOT NULL,
    Feedback        VARCHAR(255),
    ApplicationID   INT             NOT NULL,
    ConductedBy     INT             NOT NULL,
    PRIMARY KEY (InterviewID),
    FOREIGN KEY (ApplicationID) REFERENCES APPLICATION (ApplicationID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (ConductedBy) REFERENCES HIRING_MANAGER (EmployeeID)
        ON DELETE RESTRICT ON UPDATE CASCADE );

CREATE TABLE CANDIDATE_RANKING (
    RankingID       INT             NOT NULL,
    Score           DECIMAL(5,2)    NOT NULL CHECK (Score >= 0 AND Score <= 100),
    RankPosition    INT             NOT NULL CHECK (RankPosition > 0),
    ApplicationID   INT             NOT NULL,
    PRIMARY KEY (RankingID),
    UNIQUE (ApplicationID),
    FOREIGN KEY (ApplicationID) REFERENCES APPLICATION (ApplicationID)
        ON DELETE CASCADE ON UPDATE CASCADE );

CREATE TABLE JOB_OFFER (
    OfferID         INT             NOT NULL,
    Salary          DECIMAL(10,2)   NOT NULL CHECK (Salary > 0),
    StartDate       DATE            NOT NULL,
    ApplicationID   INT             NOT NULL,
    PRIMARY KEY (OfferID),
    UNIQUE (ApplicationID),
    FOREIGN KEY (ApplicationID) REFERENCES APPLICATION (ApplicationID)
        ON DELETE CASCADE ON UPDATE CASCADE );

-- Junction table for the M:N relationship "Sent Using".
-- SentDate is part of the key so the same template can be sent to the
-- same application more than once.
CREATE TABLE SENT_EMAIL (
    ApplicationID   INT             NOT NULL,
    TemplateID      INT             NOT NULL,
    SentDate        DATETIME        NOT NULL,
    PRIMARY KEY (ApplicationID, TemplateID, SentDate),
    FOREIGN KEY (ApplicationID) REFERENCES APPLICATION (ApplicationID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (TemplateID) REFERENCES EMAIL_TEMPLATE (TemplateID)
        ON DELETE RESTRICT ON UPDATE CASCADE );

-- =====================================================================
-- SECTION 2: SAMPLE DATA
-- =====================================================================


-- Departments (20 rows)
INSERT INTO DEPARTMENT (DepartmentID, Name, Location) VALUES
  (1, 'Engineering', 'Blacksburg, VA'),
  (2, 'Data Science', 'Arlington, VA'),
  (3, 'Product Management', 'Blacksburg, VA'),
  (4, 'Marketing', 'Richmond, VA'),
  (5, 'Human Resources', 'Blacksburg, VA'),
  (6, 'Finance', 'Arlington, VA'),
  (7, 'Sales', 'Richmond, VA'),
  (8, 'Customer Success', 'Roanoke, VA'),
  (9, 'Legal', 'Arlington, VA'),
  (10, 'Information Security', 'Blacksburg, VA'),
  (11, 'Quality Assurance', 'Roanoke, VA'),
  (12, 'IT Operations', 'Blacksburg, VA'),
  (13, 'Business Intelligence', 'Arlington, VA'),
  (14, 'Design', 'Richmond, VA'),
  (15, 'Corporate Communications', 'Arlington, VA'),
  (16, 'Facilities', 'Roanoke, VA'),
  (17, 'Procurement', 'Richmond, VA'),
  (18, 'Research and Development', 'Blacksburg, VA'),
  (19, 'Partnerships', 'Arlington, VA'),
  (20, 'Training and Development', 'Roanoke, VA');

-- Recruiters (20 rows)
INSERT INTO RECRUITER (EmployeeID, Name, Email) VALUES
  (101, 'Maya Thompson', 'mthompson@hiretrack.com'),
  (102, 'Daniel Okafor', 'dokafor@hiretrack.com'),
  (103, 'Priya Raman', 'praman@hiretrack.com'),
  (104, 'Lucas Fernandez', 'lfernandez@hiretrack.com'),
  (105, 'Hannah Berg', 'hberg@hiretrack.com'),
  (106, 'Omar Haddad', 'ohaddad@hiretrack.com'),
  (107, 'Sofia Mancini', 'smancini@hiretrack.com'),
  (108, 'Ethan Brooks', 'ebrooks@hiretrack.com'),
  (109, 'Leila Nasser', 'lnasser@hiretrack.com'),
  (110, 'Marcus Webb', 'mwebb@hiretrack.com'),
  (111, 'Anya Volkov', 'avolkov@hiretrack.com'),
  (112, 'Caleb Stone', 'cstone@hiretrack.com'),
  (113, 'Ingrid Dahl', 'idahl@hiretrack.com'),
  (114, 'Rafael Costa', 'rcosta@hiretrack.com'),
  (115, 'Noor Siddiqui', 'nsiddiqui@hiretrack.com'),
  (116, 'Trevor Lane', 'tlane@hiretrack.com'),
  (117, 'Yara Mansour', 'ymansour@hiretrack.com'),
  (118, 'Peter Nowak', 'pnowak@hiretrack.com'),
  (119, 'Camille Dubois', 'cdubois@hiretrack.com'),
  (120, 'Andre Bakker', 'abakker@hiretrack.com');

-- Candidates (25 rows)
INSERT INTO CANDIDATE (CandidateID, Name, Email, Type) VALUES
  (301, 'Aaron Abbott', 'aabbott@example.com', 'External'),
  (302, 'Bianca Barros', 'bbarros@example.com', 'External'),
  (303, 'Chen Castellanos', 'ccastellanos@example.com', 'Internal'),
  (304, 'Dalia Duarte', 'dduarte@example.com', 'Referral'),
  (305, 'Elias Ellison', 'eellison@example.com', 'External'),
  (306, 'Farida Fontaine', 'ffontaine@example.com', 'External'),
  (307, 'Grace Gallagher', 'ggallagher@example.com', 'External'),
  (308, 'Hugo Hoang', 'hhoang@example.com', 'Internal'),
  (309, 'Imani Ivanov', 'iivanov@example.com', 'Referral'),
  (310, 'Jonas Jensen', 'jjensen@example.com', 'External'),
  (311, 'Keiko Kowalski', 'kkowalski@example.com', 'External'),
  (312, 'Liam Lindqvist', 'llindqvist@example.com', 'External'),
  (313, 'Marisol Moreau', 'mmoreau@example.com', 'Internal'),
  (314, 'Nikhil Nakamura', 'nnakamura@example.com', 'Referral'),
  (315, 'Olivia Oyelaran', 'ooyelaran@example.com', 'External'),
  (316, 'Pavel Petrov', 'ppetrov@example.com', 'External'),
  (317, 'Quinn Quintero', 'qquintero@example.com', 'External'),
  (318, 'Rosa Rhodes', 'rrhodes@example.com', 'Internal'),
  (319, 'Samir Silva', 'ssilva@example.com', 'Referral'),
  (320, 'Tessa Tanaka', 'ttanaka@example.com', 'External'),
  (321, 'Umar Ucar', 'uucar@example.com', 'External'),
  (322, 'Valeria Vasquez', 'vvasquez@example.com', 'External'),
  (323, 'Wesley Whelan', 'wwhelan@example.com', 'Internal'),
  (324, 'Ximena Xiong', 'xxiong@example.com', 'Referral'),
  (325, 'Yusuf Yilmaz', 'yyilmaz@example.com', 'External');

-- Hiring pipeline stages (7 rows)
INSERT INTO HIRING_STATUS (StatusID, StatusName, StageOrder) VALUES
  (1, 'Submitted', 1),
  (2, 'Under Review', 2),
  (3, 'Screening', 3),
  (4, 'Interviewing', 4),
  (5, 'Offer Extended', 5),
  (6, 'Hired', 6),
  (7, 'Rejected', 7);

-- Email templates (20 rows)
INSERT INTO EMAIL_TEMPLATE (TemplateID, Subject, Body) VALUES
  (1, 'We received your application', 'Thank you for applying. Our team is reviewing your materials and will be in touch.'),
  (2, 'Next steps in your application', 'Your application has passed initial screening. A recruiter will contact you shortly.'),
  (3, 'Interview invitation', 'We would like to invite you to interview for this position. Please select a time.'),
  (4, 'Reminder: your upcoming interview', 'This is a reminder about your interview scheduled with our team.'),
  (5, 'Your offer from HireTrack', 'We are pleased to extend you an offer. Details are attached for your review.'),
  (6, 'Update on your application', 'After careful review we have decided to move forward with other candidates.'),
  (7, 'Confirming your withdrawal', 'We have recorded your request to withdraw from this process.'),
  (8, 'Complete your skills assessment', 'Please complete the online assessment linked below within five days.'),
  (9, 'Reference check for your application', 'We are requesting references as part of the final stage of review.'),
  (10, 'Background check authorization', 'Please authorize a standard background check to proceed with your offer.'),
  (11, 'Welcome to the team', 'We are excited to have you join. Onboarding details follow.'),
  (12, 'Your interview has been rescheduled', 'Your interview time has changed. The updated details are below.'),
  (13, 'Invitation to a panel interview', 'You are invited to meet with a panel of team members.'),
  (14, 'Invitation to the final round', 'You have advanced to the final round of interviews.'),
  (15, 'Your offer expires soon', 'A reminder that your offer requires a response by the stated deadline.'),
  (16, 'Thank you for accepting', 'We have received your acceptance and will be in touch about start details.'),
  (17, 'Sorry to see you go', 'We have recorded your decision to decline the offer. We wish you well.'),
  (18, 'Joining our talent community', 'We would like to keep your profile for future openings.'),
  (19, 'This position has been filled', 'The role you applied for has now been filled.'),
  (20, 'How was your interview experience?', 'We would value your feedback on the interview process.');

-- Hiring managers, each working in a department (20 rows)
INSERT INTO HIRING_MANAGER (EmployeeID, Name, Email, DepartmentID) VALUES
  (201, 'Evelyn Shaw', 'eshaw@hiretrack.com', 1),
  (202, 'Rajesh Nair', 'rnair@hiretrack.com', 2),
  (203, 'Clara Whitfield', 'cwhitfield@hiretrack.com', 3),
  (204, 'Tobias Lund', 'tlund@hiretrack.com', 4),
  (205, 'Naomi Price', 'nprice@hiretrack.com', 5),
  (206, 'Victor Alvarez', 'valvarez@hiretrack.com', 6),
  (207, 'Gloria Mbeki', 'gmbeki@hiretrack.com', 7),
  (208, 'Henrik Olsen', 'holsen@hiretrack.com', 8),
  (209, 'Tanya Kapoor', 'tkapoor@hiretrack.com', 9),
  (210, 'Simon Reyes', 'sreyes@hiretrack.com', 10),
  (211, 'Adaeze Nwosu', 'anwosu@hiretrack.com', 11),
  (212, 'Felix Braun', 'fbraun@hiretrack.com', 12),
  (213, 'Monica Esposito', 'mesposito@hiretrack.com', 13),
  (214, 'Darius Kane', 'dkane@hiretrack.com', 14),
  (215, 'Ruth Levinson', 'rlevinson@hiretrack.com', 15),
  (216, 'Ibrahim Toure', 'itoure@hiretrack.com', 16),
  (217, 'Wendy Carlisle', 'wcarlisle@hiretrack.com', 17),
  (218, 'Jonah Pratt', 'jpratt@hiretrack.com', 18),
  (219, 'Sylvia Meyer', 'smeyer@hiretrack.com', 1),
  (220, 'Arjun Desai', 'adesai@hiretrack.com', 2);

-- Analytics reports (20 rows)
INSERT INTO ANALYTICS_REPORT (ReportID, ReportType, GeneratedDate, GeneratedBy) VALUES
  (5001, 'Time to Hire', '2026-07-01', 101),
  (5002, 'Applications per Posting', '2026-07-06', 102),
  (5003, 'Open Positions', '2026-07-11', 103),
  (5004, 'Pipeline Conversion', '2026-07-16', 104),
  (5005, 'Offer Acceptance', '2026-07-21', 105),
  (5006, 'Time to Hire', '2026-07-26', 106),
  (5007, 'Applications per Posting', '2026-07-31', 107),
  (5008, 'Open Positions', '2026-08-05', 108),
  (5009, 'Pipeline Conversion', '2026-08-10', 109),
  (5010, 'Offer Acceptance', '2026-08-15', 110),
  (5011, 'Time to Hire', '2026-08-20', 111),
  (5012, 'Applications per Posting', '2026-08-25', 112),
  (5013, 'Open Positions', '2026-08-30', 113),
  (5014, 'Pipeline Conversion', '2026-09-04', 114),
  (5015, 'Offer Acceptance', '2026-09-09', 115),
  (5016, 'Time to Hire', '2026-09-14', 116),
  (5017, 'Applications per Posting', '2026-09-19', 117),
  (5018, 'Open Positions', '2026-09-24', 118),
  (5019, 'Pipeline Conversion', '2026-09-29', 119),
  (5020, 'Offer Acceptance', '2026-10-04', 120);

-- Job postings, a few have no approver yet (22 rows)
INSERT INTO JOB_POSTING (JobID, Title, Description, DepartmentID, PostedBy, ApprovedBy) VALUES
  (1, 'Backend Engineer', 'Design and maintain server-side services and APIs.', 1, 102, 201),
  (2, 'Machine Learning Engineer', 'Build and deploy models that support product features.', 2, 103, 202),
  (3, 'Product Manager', 'Own the roadmap and requirements for a product area.', 3, 104, 203),
  (4, 'Growth Marketer', 'Plan and run campaigns that grow the customer base.', 4, 105, 204),
  (5, 'HR Business Partner', 'Advise managers on staffing, performance and policy.', 5, 106, 205),
  (6, 'Financial Analyst', 'Prepare forecasts, budgets and variance analysis.', 6, 107, 206),
  (7, 'Account Executive', 'Manage the sales cycle from prospecting through close.', 7, 108, 207),
  (8, 'Customer Success Manager', 'Support accounts after onboarding and drive renewals.', 8, 109, 208),
  (9, 'Paralegal', 'Prepare contracts and support the legal team with filings.', 9, 110, 209),
  (10, 'Security Analyst', 'Monitor systems and respond to security incidents.', 10, 111, 210),
  (11, 'QA Engineer', 'Write and automate tests across the product suite.', 11, 112, 211),
  (12, 'Systems Administrator', 'Maintain internal servers, accounts and backups.', 12, 113, 212),
  (13, 'BI Developer', 'Build dashboards and reporting pipelines for the business.', 13, 114, 213),
  (14, 'Product Designer', 'Design interfaces and prototypes for new features.', 14, 115, 214),
  (15, 'Communications Lead', 'Manage external messaging and press relationships.', 15, 116, 215),
  (16, 'Facilities Coordinator', 'Coordinate office space, vendors and maintenance.', 16, 117, 216),
  (17, 'Procurement Specialist', 'Source vendors and manage purchasing agreements.', 17, 118, 217),
  (18, 'Research Scientist', 'Investigate new methods and publish internal findings.', 18, 119, 218),
  (19, 'Partnerships Manager', 'Develop and manage strategic partner relationships.', 19, 120, NULL),
  (20, 'Training Specialist', 'Design and deliver internal training programs.', 20, 101, NULL),
  (21, 'Data Engineer', 'Build and maintain data pipelines and warehouses.', 1, 102, 201),
  (22, 'UX Researcher', 'Run studies that inform product and design decisions.', 2, 103, 202);

-- Applications (40 rows)
INSERT INTO APPLICATION (ApplicationID, SubmissionDate, ResumeLink, CandidateID, JobID, StatusID) VALUES
  (1001, '2026-07-25', 'https://files.hiretrack.com/resumes/1001.pdf', 318, 2, 2),
  (1002, '2026-06-08', 'https://files.hiretrack.com/resumes/1002.pdf', 301, 4, 2),
  (1003, '2026-06-05', 'https://files.hiretrack.com/resumes/1003.pdf', 312, 11, 6),
  (1004, '2026-06-04', 'https://files.hiretrack.com/resumes/1004.pdf', 317, 20, 4),
  (1005, '2026-07-31', 'https://files.hiretrack.com/resumes/1005.pdf', 323, 2, 6),
  (1006, '2026-08-10', 'https://files.hiretrack.com/resumes/1006.pdf', 324, 5, 1),
  (1007, '2026-07-13', 'https://files.hiretrack.com/resumes/1007.pdf', 325, 12, 5),
  (1008, '2026-07-29', 'https://files.hiretrack.com/resumes/1008.pdf', 304, 17, 5),
  (1009, '2026-07-15', 'https://files.hiretrack.com/resumes/1009.pdf', 313, 11, 1),
  (1010, '2026-07-11', 'https://files.hiretrack.com/resumes/1010.pdf', 310, 2, 5),
  (1011, '2026-06-25', 'https://files.hiretrack.com/resumes/1011.pdf', 310, 20, 5),
  (1012, '2026-07-21', 'https://files.hiretrack.com/resumes/1012.pdf', 302, 16, 4),
  (1013, '2026-07-22', 'https://files.hiretrack.com/resumes/1013.pdf', 320, 20, 6),
  (1014, '2026-07-19', 'https://files.hiretrack.com/resumes/1014.pdf', 308, 14, 5),
  (1015, '2026-07-16', 'https://files.hiretrack.com/resumes/1015.pdf', 316, 13, 6),
  (1016, '2026-07-16', 'https://files.hiretrack.com/resumes/1016.pdf', 319, 22, 7),
  (1017, '2026-07-22', 'https://files.hiretrack.com/resumes/1017.pdf', 317, 14, 6),
  (1018, '2026-06-30', 'https://files.hiretrack.com/resumes/1018.pdf', 304, 22, 7),
  (1019, '2026-06-04', 'https://files.hiretrack.com/resumes/1019.pdf', 314, 10, 3),
  (1020, '2026-06-17', 'https://files.hiretrack.com/resumes/1020.pdf', 305, 9, 7),
  (1021, '2026-06-03', 'https://files.hiretrack.com/resumes/1021.pdf', 306, 14, 6),
  (1022, '2026-06-24', 'https://files.hiretrack.com/resumes/1022.pdf', 310, 4, 4),
  (1023, '2026-07-01', 'https://files.hiretrack.com/resumes/1023.pdf', 317, 2, 5),
  (1024, '2026-07-31', 'https://files.hiretrack.com/resumes/1024.pdf', 306, 6, 6),
  (1025, '2026-07-27', 'https://files.hiretrack.com/resumes/1025.pdf', 317, 18, 2),
  (1026, '2026-07-19', 'https://files.hiretrack.com/resumes/1026.pdf', 312, 18, 6),
  (1027, '2026-06-13', 'https://files.hiretrack.com/resumes/1027.pdf', 304, 15, 5),
  (1028, '2026-06-22', 'https://files.hiretrack.com/resumes/1028.pdf', 304, 4, 5),
  (1029, '2026-07-21', 'https://files.hiretrack.com/resumes/1029.pdf', 314, 21, 4),
  (1030, '2026-07-10', 'https://files.hiretrack.com/resumes/1030.pdf', 313, 22, 7),
  (1031, '2026-08-09', 'https://files.hiretrack.com/resumes/1031.pdf', 319, 12, 3),
  (1032, '2026-06-04', 'https://files.hiretrack.com/resumes/1032.pdf', 317, 16, 4),
  (1033, '2026-06-21', 'https://files.hiretrack.com/resumes/1033.pdf', 325, 20, 3),
  (1034, '2026-06-27', 'https://files.hiretrack.com/resumes/1034.pdf', 308, 10, 6),
  (1035, '2026-07-01', 'https://files.hiretrack.com/resumes/1035.pdf', 325, 7, 4),
  (1036, '2026-07-20', 'https://files.hiretrack.com/resumes/1036.pdf', 301, 17, 4),
  (1037, '2026-07-25', 'https://files.hiretrack.com/resumes/1037.pdf', 323, 15, 5),
  (1038, '2026-07-19', 'https://files.hiretrack.com/resumes/1038.pdf', 303, 22, 6),
  (1039, '2026-08-05', 'https://files.hiretrack.com/resumes/1039.pdf', 325, 6, 5),
  (1040, '2026-07-11', 'https://files.hiretrack.com/resumes/1040.pdf', 301, 10, 1);

-- Interviews (27 rows)
INSERT INTO INTERVIEW (InterviewID, ScheduledDate, Feedback, ApplicationID, ConductedBy) VALUES
  (2001, '2026-06-12 10:00:00', 'Thoughtful answers, would benefit from more leadership exposure.', 1003, 211),
  (2002, '2026-06-11 10:00:00', 'Thoughtful answers, would benefit from more leadership exposure.', 1004, 211),
  (2003, '2026-08-07 10:00:00', 'Good problem solving but struggled with follow-up questions.', 1005, 220),
  (2004, '2026-07-20 10:00:00', 'Excellent collaboration signals, moderate domain knowledge.', 1007, 212),
  (2005, '2026-08-05 10:00:00', NULL, 1008, 217),
  (2006, '2026-07-18 10:00:00', 'Strong technical depth, communicates tradeoffs clearly.', 1010, 220),
  (2007, '2026-07-02 10:00:00', NULL, 1011, 214),
  (2008, '2026-07-28 10:00:00', 'Strong technical depth, communicates tradeoffs clearly.', 1012, 216),
  (2009, '2026-07-29 10:00:00', 'Strong technical depth, communicates tradeoffs clearly.', 1013, 205),
  (2010, '2026-07-26 10:00:00', 'Clear communicator, strong portfolio, recommend advancing.', 1014, 214),
  (2011, '2026-07-23 10:00:00', NULL, 1015, 213),
  (2012, '2026-07-29 10:00:00', 'Good problem solving but struggled with follow-up questions.', 1017, 214),
  (2013, '2026-06-10 10:00:00', 'Good problem solving but struggled with follow-up questions.', 1021, 214),
  (2014, '2026-07-01 10:00:00', 'Clear communicator, strong portfolio, recommend advancing.', 1022, 204),
  (2015, '2026-07-08 10:00:00', 'Solid fundamentals, needs more systems design experience.', 1023, 202),
  (2016, '2026-08-07 10:00:00', 'Solid fundamentals, needs more systems design experience.', 1024, 206),
  (2017, '2026-07-26 10:00:00', 'Thoughtful answers, would benefit from more leadership exposure.', 1026, 218),
  (2018, '2026-06-20 10:00:00', 'Thoughtful answers, would benefit from more leadership exposure.', 1027, 215),
  (2019, '2026-06-29 10:00:00', 'Solid fundamentals, needs more systems design experience.', 1028, 204),
  (2020, '2026-07-28 10:00:00', NULL, 1029, 219),
  (2021, '2026-06-11 10:00:00', NULL, 1032, 216),
  (2022, '2026-07-04 10:00:00', 'Good problem solving but struggled with follow-up questions.', 1034, 210),
  (2023, '2026-07-08 10:00:00', 'Strong technical depth, communicates tradeoffs clearly.', 1035, 207),
  (2024, '2026-07-27 10:00:00', 'Excellent collaboration signals, moderate domain knowledge.', 1036, 217),
  (2025, '2026-08-01 10:00:00', 'Strong technical depth, communicates tradeoffs clearly.', 1037, 215),
  (2026, '2026-07-26 10:00:00', 'Thoughtful answers, would benefit from more leadership exposure.', 1038, 202),
  (2027, '2026-08-12 10:00:00', 'Good problem solving but struggled with follow-up questions.', 1039, 206);

-- Candidate rankings (33 rows)
INSERT INTO CANDIDATE_RANKING (RankingID, Score, RankPosition, ApplicationID) VALUES
  (3001, 76.43, 1, 1005),
  (3002, 72.85, 2, 1023),
  (3003, 67.31, 3, 1001),
  (3004, 58.17, 4, 1010),
  (3005, 87.12, 1, 1028),
  (3006, 79.05, 2, 1002),
  (3007, 75.91, 3, 1022),
  (3008, 95.12, 1, 1003),
  (3009, 84.76, 1, 1004),
  (3010, 74.61, 2, 1011),
  (3011, 58.82, 3, 1033),
  (3012, 56.75, 4, 1013),
  (3013, 84.56, 1, 1007),
  (3014, 61.01, 2, 1031),
  (3015, 90.33, 1, 1008),
  (3016, 70.96, 2, 1036),
  (3017, 96.16, 1, 1012),
  (3018, 77.24, 2, 1032),
  (3019, 73.64, 1, 1021),
  (3020, 70.45, 2, 1014),
  (3021, 67.74, 3, 1017),
  (3022, 69.38, 1, 1015),
  (3023, 80.71, 1, 1034),
  (3024, 72.42, 2, 1019),
  (3025, 92.98, 1, 1024),
  (3026, 71.27, 2, 1039),
  (3027, 97.48, 1, 1026),
  (3028, 58.6, 2, 1025),
  (3029, 78.62, 1, 1027),
  (3030, 71.81, 2, 1037),
  (3031, 58.47, 1, 1029),
  (3032, 56.14, 1, 1035),
  (3033, 91.44, 1, 1038);

-- Job offers (20 rows)
INSERT INTO JOB_OFFER (OfferID, Salary, StartDate, ApplicationID) VALUES
  (4001, 162115.87, '2026-09-14', 1003),
  (4002, 158583.04, '2026-11-01', 1005),
  (4003, 131541.92, '2026-10-11', 1007),
  (4004, 159650.95, '2026-11-09', 1008),
  (4005, 154086.95, '2026-10-07', 1010),
  (4006, 95489.98, '2026-10-10', 1011),
  (4007, 123671.37, '2026-10-28', 1013),
  (4008, 127926.99, '2026-11-01', 1014),
  (4009, 73555.75, '2026-10-12', 1015),
  (4010, 97265.26, '2026-11-07', 1017),
  (4011, 126101.67, '2026-09-15', 1021),
  (4012, 164917.83, '2026-10-02', 1023),
  (4013, 113313.7, '2026-10-09', 1024),
  (4014, 156354.5, '2026-10-03', 1026),
  (4015, 160600.32, '2026-09-04', 1027),
  (4016, 129209.36, '2026-09-20', 1028),
  (4017, 111245.98, '2026-09-25', 1034),
  (4018, 128283.77, '2026-10-27', 1037),
  (4019, 131581.8, '2026-10-23', 1038),
  (4020, 83469.92, '2026-11-19', 1039);

-- Sent emails (40 rows)
INSERT INTO SENT_EMAIL (ApplicationID, TemplateID, SentDate) VALUES
  (1001, 1, '2026-07-25 09:15:00'),
  (1002, 1, '2026-06-08 09:15:00'),
  (1003, 1, '2026-06-05 09:15:00'),
  (1004, 1, '2026-06-04 09:15:00'),
  (1005, 1, '2026-07-31 09:15:00'),
  (1006, 1, '2026-08-10 09:15:00'),
  (1007, 1, '2026-07-13 09:15:00'),
  (1008, 1, '2026-07-29 09:15:00'),
  (1009, 1, '2026-07-15 09:15:00'),
  (1010, 1, '2026-07-11 09:15:00'),
  (1011, 1, '2026-06-25 09:15:00'),
  (1012, 1, '2026-07-21 09:15:00'),
  (1013, 1, '2026-07-22 09:15:00'),
  (1014, 1, '2026-07-19 09:15:00'),
  (1015, 1, '2026-07-16 09:15:00'),
  (1016, 1, '2026-07-16 09:15:00'),
  (1017, 1, '2026-07-22 09:15:00'),
  (1018, 1, '2026-06-30 09:15:00'),
  (1019, 1, '2026-06-04 09:15:00'),
  (1020, 1, '2026-06-17 09:15:00'),
  (1021, 1, '2026-06-03 09:15:00'),
  (1022, 1, '2026-06-24 09:15:00'),
  (1023, 1, '2026-07-01 09:15:00'),
  (1024, 1, '2026-07-31 09:15:00'),
  (1025, 1, '2026-07-27 09:15:00'),
  (1026, 1, '2026-07-19 09:15:00'),
  (1027, 1, '2026-06-13 09:15:00'),
  (1028, 1, '2026-06-22 09:15:00'),
  (1029, 1, '2026-07-21 09:15:00'),
  (1030, 1, '2026-07-10 09:15:00'),
  (1031, 1, '2026-08-09 09:15:00'),
  (1032, 1, '2026-06-04 09:15:00'),
  (1033, 1, '2026-06-21 09:15:00'),
  (1034, 1, '2026-06-27 09:15:00'),
  (1035, 1, '2026-07-01 09:15:00'),
  (1036, 1, '2026-07-20 09:15:00'),
  (1037, 1, '2026-07-25 09:15:00'),
  (1038, 1, '2026-07-19 09:15:00'),
  (1039, 1, '2026-08-05 09:15:00'),
  (1040, 1, '2026-07-11 09:15:00');

-- =====================================================================
-- SECTION 4: USER ACCOUNTS  (final phase - user support)
-- Application users live in the database, not in the source code.
-- Passwords are stored only as a hash, never in plain text.
-- A user is linked to the person they are: a Candidate row, a
-- Recruiter row or a Hiring Manager row. An Admin is linked to none.
--
-- Note: MySQL forbids ON DELETE / ON UPDATE referential actions on a
-- column that a CHECK constraint also inspects, so these three foreign
-- keys use the default (RESTRICT). A person row therefore cannot be
-- deleted while a login still points at it.
-- =====================================================================

CREATE TABLE USER_ACCOUNT (
    UserID          INT             NOT NULL,
    Username        VARCHAR(40)     NOT NULL,
    PasswordHash    VARCHAR(255)    NOT NULL,
    Role            VARCHAR(20)     NOT NULL
                    CHECK (Role IN ('Admin','Recruiter','Hiring Manager','Candidate')),
    MustChangePassword INT          NOT NULL DEFAULT 0
                    CHECK (MustChangePassword IN (0,1)),
    CandidateID     INT,
    RecruiterID     INT,
    ManagerID       INT,
    PRIMARY KEY (UserID),
    UNIQUE (Username),
    -- exactly one person link, and it has to match the role
    CONSTRAINT chk_user_role_link CHECK (
        (Role = 'Candidate'
             AND CandidateID IS NOT NULL
             AND RecruiterID IS NULL AND ManagerID IS NULL)
     OR (Role = 'Recruiter'
             AND RecruiterID IS NOT NULL
             AND CandidateID IS NULL AND ManagerID IS NULL)
     OR (Role = 'Hiring Manager'
             AND ManagerID IS NOT NULL
             AND CandidateID IS NULL AND RecruiterID IS NULL)
     OR (Role = 'Admin'
             AND CandidateID IS NULL
             AND RecruiterID IS NULL AND ManagerID IS NULL)
    ),
    FOREIGN KEY (CandidateID) REFERENCES CANDIDATE (CandidateID),
    FOREIGN KEY (RecruiterID) REFERENCES RECRUITER (EmployeeID),
    FOREIGN KEY (ManagerID)   REFERENCES HIRING_MANAGER (EmployeeID)
) ;

-- The first admin is the only account created by hand. Everyone else
-- signs up through the application, and admins are created in-app by
-- an existing admin.
--   username: admin
--   password: admin123   <- MustChangePassword = 1 forces a reset at first login
INSERT INTO USER_ACCOUNT
    (UserID, Username, PasswordHash, Role, MustChangePassword,
     CandidateID, RecruiterID, ManagerID) VALUES
  (1, 'admin', 'pbkdf2:sha256:1000000$t87NE6nMWxWLxIAt$a0d08e85a95f3c198a2843b0c42022de9af4a959662aead6e430e8433190e933', 'Admin', 1, NULL, NULL, NULL);


-- =====================================================================
-- SECTION 3: VERIFICATION QUERIES
-- Highlight one query and press Ctrl+Enter to run just that one.
-- =====================================================================

-- Q1: How many tuples are in each table?
SELECT 'DEPARTMENT' AS TableName, COUNT(*) AS NumRows FROM DEPARTMENT
UNION ALL SELECT 'RECRUITER',         COUNT(*) FROM RECRUITER
UNION ALL SELECT 'CANDIDATE',         COUNT(*) FROM CANDIDATE
UNION ALL SELECT 'HIRING_STATUS',     COUNT(*) FROM HIRING_STATUS
UNION ALL SELECT 'EMAIL_TEMPLATE',    COUNT(*) FROM EMAIL_TEMPLATE
UNION ALL SELECT 'HIRING_MANAGER',    COUNT(*) FROM HIRING_MANAGER
UNION ALL SELECT 'ANALYTICS_REPORT',  COUNT(*) FROM ANALYTICS_REPORT
UNION ALL SELECT 'JOB_POSTING',       COUNT(*) FROM JOB_POSTING
UNION ALL SELECT 'APPLICATION',       COUNT(*) FROM APPLICATION
UNION ALL SELECT 'INTERVIEW',         COUNT(*) FROM INTERVIEW
UNION ALL SELECT 'CANDIDATE_RANKING', COUNT(*) FROM CANDIDATE_RANKING
UNION ALL SELECT 'JOB_OFFER',         COUNT(*) FROM JOB_OFFER
UNION ALL SELECT 'SENT_EMAIL',        COUNT(*) FROM SENT_EMAIL;


-- Q2: Ranked candidate list for every posting.
SELECT      JP.Title, C.Name, CR.Score, CR.RankPosition, HS.StatusName
FROM        CANDIDATE_RANKING AS CR, APPLICATION AS A, CANDIDATE AS C,
            JOB_POSTING AS JP, HIRING_STATUS AS HS
WHERE       CR.ApplicationID = A.ApplicationID
  AND       A.CandidateID    = C.CandidateID
  AND       A.JobID          = JP.JobID
  AND       A.StatusID       = HS.StatusID
ORDER BY    JP.Title, CR.RankPosition;


-- Q3: Every interview, with the candidate, the posting and the interviewer.
SELECT      I.ScheduledDate, C.Name AS Candidate, JP.Title,
            M.Name AS Interviewer, D.Name AS Department
FROM        INTERVIEW AS I, APPLICATION AS A, CANDIDATE AS C,
            JOB_POSTING AS JP, HIRING_MANAGER AS M, DEPARTMENT AS D
WHERE       I.ApplicationID = A.ApplicationID
  AND       A.CandidateID   = C.CandidateID
  AND       A.JobID         = JP.JobID
  AND       I.ConductedBy   = M.EmployeeID
  AND       M.DepartmentID  = D.DepartmentID
ORDER BY    I.ScheduledDate;
