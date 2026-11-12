-- REVIEW-ONLY SQL. DO NOT APPLY to existing Render database automatically.
-- Run as database administrator on an approved isolated staging database.
-- Assumes public.research_run_registry exists after separately approved migration.
-- Runtime role must have NO write privileges; never use the owner/migration role.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'alpha_research_reader') THEN
    CREATE ROLE alpha_research_reader NOLOGIN;
  END IF;
END $$;
REVOKE ALL ON TABLE public.research_run_registry FROM PUBLIC;
REVOKE ALL ON TABLE public.research_run_registry FROM alpha_research_reader;
GRANT USAGE ON SCHEMA public TO alpha_research_reader;
GRANT SELECT (owner_id, run_id, evidence_sha256, created_at)
  ON TABLE public.research_run_registry TO alpha_research_reader;
-- IMPORTANT: row ownership must also be enforced by a trusted owner-scoped query
-- and preferably RLS with a dedicated per-request verified owner context.
-- This role alone does not provide row-level tenant isolation.
