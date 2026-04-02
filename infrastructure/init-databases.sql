-- =============================================================================
-- Al-Mizan Backend: PostgreSQL Initialization Script
-- This script runs automatically on first container startup
-- Creates all service databases and their dedicated users
-- =============================================================================

-- Auth Service
CREATE USER auth_user WITH PASSWORD 'auth_password';
CREATE DATABASE auth_db OWNER auth_user;
GRANT ALL PRIVILEGES ON DATABASE auth_db TO auth_user;

-- Acteurs Service
CREATE USER acteurs_user WITH PASSWORD 'acteurs_password';
CREATE DATABASE acteurs_db OWNER acteurs_user;
GRANT ALL PRIVILEGES ON DATABASE acteurs_db TO acteurs_user;

-- Appels Service
CREATE USER appels_user WITH PASSWORD 'appels_password';
CREATE DATABASE appels_db OWNER appels_user;
GRANT ALL PRIVILEGES ON DATABASE appels_db TO appels_user;

-- Audit Service (CQRS with separate write/read databases)
CREATE USER audit_user WITH PASSWORD 'audit_password';
CREATE DATABASE audit_ledger OWNER audit_user;
CREATE DATABASE audit_read OWNER audit_user;
GRANT ALL PRIVILEGES ON DATABASE audit_ledger TO audit_user;
GRANT ALL PRIVILEGES ON DATABASE audit_read TO audit_user;
ALTER USER audit_user WITH REPLICATION;

-- Contractant Service
CREATE USER contractant_user WITH PASSWORD 'contractant_password';
CREATE DATABASE contractant_db OWNER contractant_user;
GRANT ALL PRIVILEGES ON DATABASE contractant_db TO contractant_user;

-- Contrats Service
CREATE USER contrats_user WITH PASSWORD 'contrats_password';
CREATE DATABASE contrats_db OWNER contrats_user;
GRANT ALL PRIVILEGES ON DATABASE contrats_db TO contrats_user;

-- Documents Service
CREATE USER documents_user WITH PASSWORD 'documents_password';
CREATE DATABASE documents_db OWNER documents_user;
GRANT ALL PRIVILEGES ON DATABASE documents_db TO documents_user;

-- Evaluations Service
CREATE USER evaluations_user WITH PASSWORD 'evaluations_password';
CREATE DATABASE evaluations_db OWNER evaluations_user;
GRANT ALL PRIVILEGES ON DATABASE evaluations_db TO evaluations_user;

-- IA Service
CREATE USER ia_user WITH PASSWORD 'ia_password';
CREATE DATABASE ia_db OWNER ia_user;
GRANT ALL PRIVILEGES ON DATABASE ia_db TO ia_user;

-- Notifications Service
CREATE USER notifications_user WITH PASSWORD 'notifications_password';
CREATE DATABASE notifications_db OWNER notifications_user;
GRANT ALL PRIVILEGES ON DATABASE notifications_db TO notifications_user;

-- Soumissions Service
CREATE USER soumissions_user WITH PASSWORD 'soumissions_password';
CREATE DATABASE soumissions_db OWNER soumissions_user;
GRANT ALL PRIVILEGES ON DATABASE soumissions_db TO soumissions_user;

-- Recours Service (future)
CREATE USER recours_user WITH PASSWORD 'recours_password';
CREATE DATABASE recours_db OWNER recours_user;
GRANT ALL PRIVILEGES ON DATABASE recours_db TO recours_user;

-- Grant schema permissions for each database
-- (PostgreSQL 15+ requires explicit schema grants)
\connect auth_db
GRANT ALL ON SCHEMA public TO auth_user;

\connect acteurs_db
GRANT ALL ON SCHEMA public TO acteurs_user;

\connect appels_db
GRANT ALL ON SCHEMA public TO appels_user;

\connect audit_db
GRANT ALL ON SCHEMA public TO audit_user;

\connect contractant_db
GRANT ALL ON SCHEMA public TO contractant_user;

\connect contrats_db
GRANT ALL ON SCHEMA public TO contrats_user;

\connect documents_db
GRANT ALL ON SCHEMA public TO documents_user;

\connect evaluations_db
GRANT ALL ON SCHEMA public TO evaluations_user;

\connect ia_db
GRANT ALL ON SCHEMA public TO ia_user;

\connect notifications_db
GRANT ALL ON SCHEMA public TO notifications_user;

\connect soumissions_db
GRANT ALL ON SCHEMA public TO soumissions_user;

\connect recours_db
GRANT ALL ON SCHEMA public TO recours_user;
