CREATE DATABASE IF NOT EXISTS company_db;
USE company_db;
CREATE USER IF NOT EXISTS 'user'@'localhost' IDENTIFIED BY 'pass';

-- Create employee table
CREATE TABLE IF NOT EXISTS employee (
    emp_id INT AUTO_INCREMENT PRIMARY KEY,
    firstname VARCHAR(50) NOT NULL,
    lastname VARCHAR(50) NOT NULL,
    department VARCHAR(50) NOT NULL,
    residency_state VARCHAR(50) NOT NULL,
    emp_role VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE
);

-- Create projects table with foreign key to employee and contracts
CREATE TABLE IF NOT EXISTS projects (
    project_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    product_name VARCHAR(100) NOT NULL,
    contract_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES employee(emp_id),
    FOREIGN KEY (contract_id) REFERENCES contracts(contract_id)
);

-- Create contracts table with foreign key to employee
CREATE TABLE IF NOT EXISTS contracts (
    contract_id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(50) NOT NULL
);

-- Create junction table for employee-project assignments
CREATE TABLE IF NOT EXISTS employee_project (
    emp_id     INT NOT NULL,
    project_id INT NOT NULL,
    PRIMARY KEY (emp_id, project_id),
    FOREIGN KEY (emp_id)     REFERENCES employee(emp_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);


-- ----------------------------
-- CONTRACTS (5)  — insert first; no dependencies
-- ----------------------------
INSERT INTO contracts (company_name) VALUES
('Apex Solutions LLC'),
('Horizon Tech Corp'),
('Pinnacle Dynamics Inc'),
('Nexus Enterprises'),
('Vertex Global Partners');

-- ----------------------------
-- EMPLOYEES (100)  — 10 per department
-- ----------------------------
INSERT INTO employee (firstname, lastname, department, residency_state, emp_role, email) VALUES
-- Engineering (emp_id 1–10)
('James',    'Smith',      'Engineering', 'California',    'Software Engineer',        'james.smith@company.com'),
('John',     'Johnson',    'Engineering', 'Texas',         'Senior Software Engineer', 'john.johnson@company.com'),
('Robert',   'Williams',   'Engineering', 'New York',      'DevOps Engineer',          'robert.williams@company.com'),
('Michael',  'Brown',      'Engineering', 'Washington',    'QA Engineer',              'michael.brown@company.com'),
('William',  'Jones',      'Engineering', 'Oregon',        'Team Lead',                'william.jones@company.com'),
('David',    'Garcia',     'Engineering', 'Colorado',      'Software Engineer',        'david.garcia@company.com'),
('Richard',  'Miller',     'Engineering', 'Arizona',       'Software Engineer',        'richard.miller@company.com'),
('Joseph',   'Davis',      'Engineering', 'Nevada',        'Senior Software Engineer', 'joseph.davis@company.com'),
('Thomas',   'Rodriguez',  'Engineering', 'Utah',          'DevOps Engineer',          'thomas.rodriguez@company.com'),
('Charles',  'Martinez',   'Engineering', 'Idaho',         'QA Engineer',              'charles.martinez@company.com'),
-- Marketing (emp_id 11–20)
('Mary',     'Hernandez',  'Marketing',   'Florida',       'Business Analyst',         'mary.hernandez@company.com'),
('Patricia', 'Lopez',      'Marketing',   'Georgia',       'Team Lead',                'patricia.lopez@company.com'),
('Jennifer', 'Gonzalez',   'Marketing',   'North Carolina','Product Manager',          'jennifer.gonzalez@company.com'),
('Linda',    'Wilson',     'Marketing',   'Virginia',      'Data Analyst',             'linda.wilson@company.com'),
('Barbara',  'Anderson',   'Marketing',   'Ohio',          'Business Analyst',         'barbara.anderson@company.com'),
('Elizabeth','Thomas',     'Marketing',   'Michigan',      'Data Analyst',             'elizabeth.thomas@company.com'),
('Susan',    'Taylor',     'Marketing',   'Illinois',      'Product Manager',          'susan.taylor@company.com'),
('Jessica',  'Moore',      'Marketing',   'Pennsylvania',  'Business Analyst',         'jessica.moore@company.com'),
('Sarah',    'Jackson',    'Marketing',   'New Jersey',    'Product Manager',          'sarah.jackson@company.com'),
('Karen',    'Martin',     'Marketing',   'Massachusetts', 'Team Lead',                'karen.martin@company.com'),
-- Finance (emp_id 21–30)
('Daniel',   'Lee',        'Finance',     'Connecticut',   'Data Analyst',             'daniel.lee@company.com'),
('Mark',     'Perez',      'Finance',     'Maryland',      'Business Analyst',         'mark.perez@company.com'),
('Donald',   'Thompson',   'Finance',     'Minnesota',     'Data Analyst',             'donald.thompson@company.com'),
('George',   'White',      'Finance',     'Wisconsin',     'Team Lead',                'george.white@company.com'),
('Kenneth',  'Harris',     'Finance',     'Missouri',      'Business Analyst',         'kenneth.harris@company.com'),
('Steven',   'Sanchez',    'Finance',     'Tennessee',     'Data Analyst',             'steven.sanchez@company.com'),
('Edward',   'Clark',      'Finance',     'Indiana',       'Business Analyst',         'edward.clark@company.com'),
('Brian',    'Ramirez',    'Finance',     'Kentucky',      'Data Analyst',             'brian.ramirez@company.com'),
('Ronald',   'Lewis',      'Finance',     'Alabama',       'Team Lead',                'ronald.lewis@company.com'),
('Anthony',  'Robinson',   'Finance',     'Louisiana',     'Business Analyst',         'anthony.robinson@company.com'),
-- HR (emp_id 31–40)
('Kevin',    'Walker',     'HR',          'South Carolina','Project Manager',          'kevin.walker@company.com'),
('Jason',    'Young',      'HR',          'Mississippi',   'Business Analyst',         'jason.young@company.com'),
('Matthew',  'Allen',      'HR',          'Arkansas',      'Team Lead',                'matthew.allen@company.com'),
('Gary',     'King',       'HR',          'Oklahoma',      'Business Analyst',         'gary.king@company.com'),
('Timothy',  'Wright',     'HR',          'Iowa',          'Project Manager',          'timothy.wright@company.com'),
('Jose',     'Scott',      'HR',          'Kansas',        'Business Analyst',         'jose.scott@company.com'),
('Larry',    'Torres',     'HR',          'Nebraska',      'Team Lead',                'larry.torres@company.com'),
('Jeffrey',  'Nguyen',     'HR',          'New Mexico',    'Project Manager',          'jeffrey.nguyen@company.com'),
('Frank',    'Hill',       'HR',          'West Virginia', 'Business Analyst',         'frank.hill@company.com'),
('Scott',    'Flores',     'HR',          'Maine',         'Project Manager',          'scott.flores@company.com'),
-- Operations (emp_id 41–50)
('Eric',     'Green',      'Operations',  'New Hampshire', 'Team Lead',                'eric.green@company.com'),
('Stephen',  'Adams',      'Operations',  'Vermont',       'DevOps Engineer',          'stephen.adams@company.com'),
('Andrew',   'Nelson',     'Operations',  'Rhode Island',  'QA Engineer',              'andrew.nelson@company.com'),
('Raymond',  'Baker',      'Operations',  'Delaware',      'DevOps Engineer',          'raymond.baker@company.com'),
('Gregory',  'Hall',       'Operations',  'Hawaii',        'QA Engineer',              'gregory.hall@company.com'),
('Joshua',   'Rivera',     'Operations',  'Alaska',        'Team Lead',                'joshua.rivera@company.com'),
('Jerry',    'Campbell',   'Operations',  'Montana',       'DevOps Engineer',          'jerry.campbell@company.com'),
('Dennis',   'Mitchell',   'Operations',  'Wyoming',       'QA Engineer',              'dennis.mitchell@company.com'),
('Walter',   'Carter',     'Operations',  'North Dakota',  'DevOps Engineer',          'walter.carter@company.com'),
('Patrick',  'Roberts',    'Operations',  'South Dakota',  'Team Lead',                'patrick.roberts@company.com'),
-- Sales (emp_id 51–60)
('Peter',    'Phillips',   'Sales',       'California',    'Business Analyst',         'peter.phillips@company.com'),
('Harold',   'Evans',      'Sales',       'Texas',         'Team Lead',                'harold.evans@company.com'),
('Douglas',  'Turner',     'Sales',       'Florida',       'Business Analyst',         'douglas.turner@company.com'),
('Henry',    'Parker',     'Sales',       'New York',      'Product Manager',          'henry.parker@company.com'),
('Carl',     'Collins',    'Sales',       'Washington',    'Business Analyst',         'carl.collins@company.com'),
('Arthur',   'Edwards',    'Sales',       'Illinois',      'Product Manager',          'arthur.edwards@company.com'),
('Ryan',     'Stewart',    'Sales',       'Georgia',       'Team Lead',                'ryan.stewart@company.com'),
('Roger',    'Morris',     'Sales',       'Ohio',          'Business Analyst',         'roger.morris@company.com'),
('Joe',      'Rogers',     'Sales',       'Michigan',      'Product Manager',          'joe.rogers@company.com'),
('Juan',     'Reed',       'Sales',       'Arizona',       'Business Analyst',         'juan.reed@company.com'),
-- Legal (emp_id 61–70)
('Jack',     'Bailey',     'Legal',       'Colorado',      'Business Analyst',         'jack.bailey@company.com'),
('Albert',   'Bell',       'Legal',       'Nevada',        'Team Lead',                'albert.bell@company.com'),
('Jonathan', 'Gomez',      'Legal',       'Oregon',        'Business Analyst',         'jonathan.gomez@company.com'),
('Justin',   'Kelly',      'Legal',       'Utah',          'Project Manager',          'justin.kelly@company.com'),
('Terry',    'Howard',     'Legal',       'Virginia',      'Business Analyst',         'terry.howard@company.com'),
('Gerald',   'Ward',       'Legal',       'Maryland',      'Team Lead',                'gerald.ward@company.com'),
('Keith',    'Cox',        'Legal',       'Minnesota',     'Business Analyst',         'keith.cox@company.com'),
('Samuel',   'Diaz',       'Legal',       'Wisconsin',     'Project Manager',          'samuel.diaz@company.com'),
('Willie',   'Richardson', 'Legal',       'Tennessee',     'Business Analyst',         'willie.richardson@company.com'),
('Ralph',    'Wood',       'Legal',       'Indiana',       'Team Lead',                'ralph.wood@company.com'),
-- IT (emp_id 71–80)
('Lawrence', 'Watson',     'IT',          'Missouri',      'Software Engineer',        'lawrence.watson@company.com'),
('Nicholas', 'Brooks',     'IT',          'Kentucky',      'Senior Software Engineer', 'nicholas.brooks@company.com'),
('Roy',      'Bennett',    'IT',          'Alabama',       'DevOps Engineer',          'roy.bennett@company.com'),
('Benjamin', 'Gray',       'IT',          'Louisiana',     'QA Engineer',              'benjamin.gray@company.com'),
('Bruce',    'James',      'IT',          'South Carolina','Software Engineer',        'bruce.james@company.com'),
('Brandon',  'Reyes',      'IT',          'Mississippi',   'Team Lead',                'brandon.reyes@company.com'),
('Adam',     'Cruz',       'IT',          'Arkansas',      'DevOps Engineer',          'adam.cruz@company.com'),
('Harry',    'Hughes',     'IT',          'Oklahoma',      'QA Engineer',              'harry.hughes@company.com'),
('Fred',     'Price',      'IT',          'Iowa',          'Software Engineer',        'fred.price@company.com'),
('Wayne',    'Myers',      'IT',          'Kansas',        'Senior Software Engineer', 'wayne.myers@company.com'),
-- Product (emp_id 81–90)
('Billy',    'Long',       'Product',     'Nebraska',      'Product Manager',          'billy.long@company.com'),
('Steve',    'Foster',     'Product',     'New Mexico',    'UX Designer',              'steve.foster@company.com'),
('Louis',    'Sanders',    'Product',     'New Hampshire', 'Product Manager',          'louis.sanders@company.com'),
('Jeremy',   'Ross',       'Product',     'Vermont',       'UX Designer',              'jeremy.ross@company.com'),
('Aaron',    'Morales',    'Product',     'Rhode Island',  'Product Manager',          'aaron.morales@company.com'),
('Randy',    'Powell',     'Product',     'Delaware',      'UX Designer',              'randy.powell@company.com'),
('Howard',   'Sullivan',   'Product',     'Hawaii',        'Product Manager',          'howard.sullivan@company.com'),
('Eugene',   'Russell',    'Product',     'Alaska',        'UX Designer',              'eugene.russell@company.com'),
('Carlos',   'Ortiz',      'Product',     'Montana',       'Product Manager',          'carlos.ortiz@company.com'),
('Russell',  'Jenkins',    'Product',     'Wyoming',       'UX Designer',              'russell.jenkins@company.com'),
-- Design (emp_id 91–100)
('Bobby',    'Gutierrez',  'Design',      'North Dakota',  'UX Designer',              'bobby.gutierrez@company.com'),
('Victor',   'Perry',      'Design',      'South Dakota',  'UX Designer',              'victor.perry@company.com'),
('Martin',   'Butler',     'Design',      'Maine',         'Team Lead',                'martin.butler@company.com'),
('Ernest',   'Cooper',     'Design',      'West Virginia', 'UX Designer',              'ernest.cooper@company.com'),
('Phillip',  'Patterson',  'Design',      'North Carolina','UX Designer',              'phillip.patterson@company.com'),
('Todd',     'Hughes',     'Design',      'Florida',       'Team Lead',                'todd.hughes@company.com'),
('Diana',    'Fleming',    'Design',      'New York',      'UX Designer',              'diana.fleming@company.com'),
('Alice',    'Morton',     'Design',      'Texas',         'UX Designer',              'alice.morton@company.com'),
('Natalie',  'Webb',       'Design',      'Ohio',          'Senior UX Designer',       'natalie.webb@company.com'),
('Grace',    'Powell',     'Design',      'Georgia',       'UX Designer',              'grace.powell@company.com');

-- ----------------------------
-- PROJECTS (10)
-- user_id = project lead employee; 2 projects per contract
-- NOTE: contract_id column must be added to projects before running
--   ALTER TABLE projects ADD COLUMN contract_id INT NOT NULL;
-- ----------------------------
INSERT INTO projects (user_id, product_name, contract_id) VALUES
-- Contract 1 (projects 1–2)
(1,  'Customer Portal Redesign',       1),
(2,  'Mobile App Development',         1),
-- Contract 2 (projects 3–4)
(3,  'Data Analytics Platform',        2),
(4,  'Cloud Migration Initiative',     2),
-- Contract 3 (projects 5–6)
(5,  'ERP System Integration',         3),
(6,  'Cybersecurity Overhaul',         3),
-- Contract 4 (projects 7–8)
(7,  'E-Commerce Platform',            4),
(8,  'AI/ML Pipeline',                 4),
-- Contract 5 (projects 9–10)
(9,  'DevOps Automation Suite',        5),
(10, 'Compliance Management System',  5);

-- ============================================================
-- EMPLOYEE–PROJECT ASSIGNMENTS (10 employees per project)
-- ============================================================
-- The schema requires a junction table for many-to-many assignments.
-- Add this table to schema.sql, then run the INSERTs below:

CREATE TABLE IF NOT EXISTS employee_project (
    emp_id     INT NOT NULL,
    project_id INT NOT NULL,
    PRIMARY KEY (emp_id, project_id),
    FOREIGN KEY (emp_id)     REFERENCES employee(emp_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
-- ============================================================

INSERT INTO employee_project (emp_id, project_id) VALUES
-- Project 1  – Customer Portal Redesign        (Engineering, emp 1–10)
(1,1),(2,1),(3,1),(4,1),(5,1),(6,1),(7,1),(8,1),(9,1),(10,1),
-- Project 2  – Mobile App Development          (Marketing,   emp 11–20)
(11,2),(12,2),(13,2),(14,2),(15,2),(16,2),(17,2),(18,2),(19,2),(20,2),
-- Project 3  – Data Analytics Platform         (Finance,     emp 21–30)
(21,3),(22,3),(23,3),(24,3),(25,3),(26,3),(27,3),(28,3),(29,3),(30,3),
-- Project 4  – Cloud Migration Initiative      (HR,          emp 31–40)
(31,4),(32,4),(33,4),(34,4),(35,4),(36,4),(37,4),(38,4),(39,4),(40,4),
-- Project 5  – ERP System Integration          (Operations,  emp 41–50)
(41,5),(42,5),(43,5),(44,5),(45,5),(46,5),(47,5),(48,5),(49,5),(50,5),
-- Project 6  – Cybersecurity Overhaul          (Sales,       emp 51–60)
(51,6),(52,6),(53,6),(54,6),(55,6),(56,6),(57,6),(58,6),(59,6),(60,6),
-- Project 7  – E-Commerce Platform             (Legal,       emp 61–70)
(61,7),(62,7),(63,7),(64,7),(65,7),(66,7),(67,7),(68,7),(69,7),(70,7),
-- Project 8  – AI/ML Pipeline                  (IT,          emp 71–80)
(71,8),(72,8),(73,8),(74,8),(75,8),(76,8),(77,8),(78,8),(79,8),(80,8),
-- Project 9  – DevOps Automation Suite         (Product,     emp 81–90)
(81,9),(82,9),(83,9),(84,9),(85,9),(86,9),(87,9),(88,9),(89,9),(90,9),
-- Project 10 – Compliance Management System    (Design,      emp 91–100)
(91,10),(92,10),(93,10),(94,10),(95,10),(96,10),(97,10),(98,10),(99,10),(100,10);
