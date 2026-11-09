-- Isolated test fixture only. Do NOT apply to Render staging.
BEGIN;
CREATE ROLE alpha_rls_reader NOLOGIN;
CREATE ROLE alpha_rls_writer NOLOGIN;
CREATE TABLE public.research_run_registry (
 owner_id text NOT NULL, run_id text NOT NULL, evidence_sha256 text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(owner_id,run_id)
);
INSERT INTO public.research_run_registry(owner_id,run_id,evidence_sha256) VALUES
 ('owner_a','a1',repeat('a',64)),('owner_b','b1',repeat('b',64));
ALTER TABLE public.research_run_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_run_registry FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_read ON public.research_run_registry FOR SELECT TO alpha_rls_reader
 USING (owner_id = current_setting('alpha_labs.owner_id',true));
REVOKE ALL ON public.research_run_registry FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO alpha_rls_reader;
GRANT SELECT ON public.research_run_registry TO alpha_rls_reader;
SET ROLE alpha_rls_reader;
SELECT set_config('alpha_labs.owner_id','owner_a',false);
DO $$ BEGIN
 IF (SELECT count(*) FROM public.research_run_registry) <> 1 THEN
   RAISE EXCEPTION 'RLS owner_a failed';
 END IF;
 IF EXISTS (SELECT 1 FROM public.research_run_registry WHERE owner_id='owner_b') THEN
   RAISE EXCEPTION 'cross-owner data visible';
 END IF;
END $$;
SELECT set_config('alpha_labs.owner_id','owner_b',false);
DO $$ BEGIN
 IF (SELECT count(*) FROM public.research_run_registry) <> 1 THEN
   RAISE EXCEPTION 'RLS owner_b failed';
 END IF;
END $$;
RESET ROLE;
-- Privilege assertions are checked as admin.
DO $$ BEGIN
 IF has_table_privilege('alpha_rls_reader','public.research_run_registry','INSERT')
 OR has_table_privilege('alpha_rls_reader','public.research_run_registry','UPDATE')
 OR has_table_privilege('alpha_rls_reader','public.research_run_registry','DELETE')
 OR has_table_privilege('alpha_rls_reader','public.research_run_registry','TRUNCATE') THEN
  RAISE EXCEPTION 'reader has write privilege';
 END IF;
END $$;
ROLLBACK;
-- SECURITY LIMITATION: custom session GUC is settable by this DB role.
-- RLS here is defence in depth, NOT proof of tenant isolation against
-- compromised runtime SQL. Never allow arbitrary SQL through the API.
