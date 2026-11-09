-- Disposable PostgreSQL only; run as fixture administrator, never on staging.
-- Transaction-scoped tenant context prevents account ID persistence in pooled sessions.
-- RLS remains defence-in-depth: the application must not expose arbitrary SQL.
BEGIN;
CREATE ROLE alpha_tx_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE TABLE public.alpha_tx_fixture (
  owner_id text NOT NULL, run_id text NOT NULL, PRIMARY KEY(owner_id, run_id)
);
INSERT INTO public.alpha_tx_fixture VALUES ('owner_a','a1'),('owner_b','b1');
ALTER TABLE public.alpha_tx_fixture ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alpha_tx_fixture FORCE ROW LEVEL SECURITY;
CREATE POLICY alpha_tx_owner ON public.alpha_tx_fixture FOR SELECT TO alpha_tx_reader
 USING (owner_id = NULLIF(current_setting('alpha_labs.owner_id', true),''));
REVOKE ALL ON public.alpha_tx_fixture FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO alpha_tx_reader;
GRANT SELECT ON public.alpha_tx_fixture TO alpha_tx_reader;
COMMIT;

-- Missing context: zero rows, and the reader has no write privileges.
BEGIN READ ONLY;
SET LOCAL ROLE alpha_tx_reader;
DO $$ BEGIN
 IF (SELECT count(*) FROM public.alpha_tx_fixture) <> 0 THEN
   RAISE EXCEPTION 'missing context exposed data';
 END IF;
END $$;
COMMIT;

BEGIN READ ONLY;
SET LOCAL ROLE alpha_tx_reader;
SELECT set_config('alpha_labs.owner_id','owner_a',true);
DO $$ BEGIN
 IF (SELECT count(*) FROM public.alpha_tx_fixture) <> 1
 OR EXISTS (SELECT 1 FROM public.alpha_tx_fixture WHERE owner_id='owner_b') THEN
   RAISE EXCEPTION 'owner_a isolation failed';
 END IF;
END $$;
COMMIT;

-- Context must be absent on the next transaction, including pooled connection reuse.
BEGIN READ ONLY;
SET LOCAL ROLE alpha_tx_reader;
DO $$ BEGIN
 IF (SELECT count(*) FROM public.alpha_tx_fixture) <> 0 THEN
   RAISE EXCEPTION 'tenant context leaked between transactions';
 END IF;
END $$;
COMMIT;

BEGIN READ ONLY;
SET LOCAL ROLE alpha_tx_reader;
SELECT set_config('alpha_labs.owner_id','owner_b',true);
DO $$ BEGIN
 IF (SELECT count(*) FROM public.alpha_tx_fixture) <> 1
 OR EXISTS (SELECT 1 FROM public.alpha_tx_fixture WHERE owner_id='owner_a') THEN
   RAISE EXCEPTION 'owner_b isolation failed';
 END IF;
END $$;
COMMIT;

DO $$ BEGIN
 IF has_table_privilege('alpha_tx_reader','public.alpha_tx_fixture','INSERT')
 OR has_table_privilege('alpha_tx_reader','public.alpha_tx_fixture','UPDATE')
 OR has_table_privilege('alpha_tx_reader','public.alpha_tx_fixture','DELETE')
 OR has_table_privilege('alpha_tx_reader','public.alpha_tx_fixture','TRUNCATE')
 OR has_table_privilege('alpha_tx_reader','public.alpha_tx_fixture','REFERENCES')
 OR has_table_privilege('alpha_tx_reader','public.alpha_tx_fixture','TRIGGER')
 THEN RAISE EXCEPTION 'reader has excessive privileges'; END IF;
END $$;

DROP TABLE public.alpha_tx_fixture;
DROP ROLE alpha_tx_reader;
