-- Disposable PostgreSQL 16 security fixture ONLY.
-- A separate LOGIN role is used for each tenant. The caller cannot change
-- session_user to another tenant because neither login is privileged.
BEGIN;
CREATE ROLE alpha_isolated_a LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD 'ci-only-a';
CREATE ROLE alpha_isolated_b LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD 'ci-only-b';
CREATE TABLE public.alpha_role_research (
 owner_role name NOT NULL, run_id text NOT NULL, evidence_sha256 text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(owner_role,run_id)
);
INSERT INTO public.alpha_role_research(owner_role,run_id,evidence_sha256)
 VALUES ('alpha_isolated_a','a1',repeat('a',64)),('alpha_isolated_b','b1',repeat('b',64));
ALTER TABLE public.alpha_role_research ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alpha_role_research FORCE ROW LEVEL SECURITY;
CREATE POLICY alpha_role_read ON public.alpha_role_research FOR SELECT
 TO alpha_isolated_a, alpha_isolated_b USING (owner_role = SESSION_USER);
REVOKE ALL ON public.alpha_role_research FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO alpha_isolated_a,alpha_isolated_b;
GRANT SELECT ON public.alpha_role_research TO alpha_isolated_a,alpha_isolated_b;
COMMIT;
-- Admin checks: neither tenant can switch roles, bypass RLS or write.
DO $$
DECLARE r name;
BEGIN
 FOREACH r IN ARRAY ARRAY['alpha_isolated_a','alpha_isolated_b']::name[] LOOP
  IF pg_has_role(r,'alpha_isolated_a','MEMBER') AND r <> 'alpha_isolated_a'
   OR pg_has_role(r,'alpha_isolated_b','MEMBER') AND r <> 'alpha_isolated_b'
   OR (SELECT rolbypassrls OR rolsuper OR rolcreaterole FROM pg_roles WHERE rolname=r)
   OR has_table_privilege(r,'public.alpha_role_research','INSERT')
   OR has_table_privilege(r,'public.alpha_role_research','UPDATE')
   OR has_table_privilege(r,'public.alpha_role_research','DELETE') THEN
   RAISE EXCEPTION 'unsafe tenant role: %',r;
  END IF;
 END LOOP;
END $$;
-- SQL execution as tenant A: attempt to forge GUC and query owner B.
SET SESSION AUTHORIZATION alpha_isolated_a;
SELECT set_config('alpha_labs.owner_id','alpha_isolated_b',false);
DO $$ BEGIN
 IF (SELECT count(*) FROM public.alpha_role_research) <> 1
 OR EXISTS (SELECT 1 FROM public.alpha_role_research WHERE run_id='b1') THEN
  RAISE EXCEPTION 'tenant A can access tenant B';
 END IF;
END $$;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION alpha_isolated_b;
SELECT set_config('alpha_labs.owner_id','alpha_isolated_a',false);
DO $$ BEGIN
 IF (SELECT count(*) FROM public.alpha_role_research) <> 1
 OR EXISTS (SELECT 1 FROM public.alpha_role_research WHERE run_id='a1') THEN
  RAISE EXCEPTION 'tenant B can access tenant A';
 END IF;
END $$;
RESET SESSION AUTHORIZATION;
-- Cleanup is explicit; fixture runs only in disposable DB.
DROP TABLE public.alpha_role_research;
REVOKE USAGE ON SCHEMA public FROM alpha_isolated_a,alpha_isolated_b;
DROP ROLE alpha_isolated_a,alpha_isolated_b;
