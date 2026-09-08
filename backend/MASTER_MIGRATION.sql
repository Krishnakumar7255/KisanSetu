-- KisanSetu SIH - consolidated Supabase migration
-- Run this file once on a fresh/existing Supabase project.
-- It is intentionally idempotent where possible and ends by reloading PostgREST.

-- 1) Core schema
\i schema.sql

-- 2) Winning/queue/audit features
\i SIH_WINNING_FEATURES.sql
\i QUEUE_AUDIT_MIGRATION.sql

-- 3) Impact features
\i SIH_IMPACT_FEATURES.sql

-- 4) Centre registration + production hardening
\i CENTRE_REGISTRATION_REQUESTS.sql
\i PRODUCTION_HARDENING.sql
\i DISTRICT_CENTER_MASTER_FIX.sql

-- 5) Final booking RPC signature/schema-cache repair
\i BOOKING_RPC_SCHEMA_FIX.sql

NOTIFY pgrst, 'reload schema';
