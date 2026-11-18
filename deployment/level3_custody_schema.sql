-- Level 3 isolated broker custody schema (migration proposal; NOT applied).
-- Run ONLY in a dedicated Level 3 database with distinct owner, broker and auditor roles.
-- Do not reuse any existing Alpha Labs database or application role.
BEGIN;
CREATE SCHEMA IF NOT EXISTS level3_custody;
CREATE TABLE IF NOT EXISTS level3_custody.remote_nonce (
  nonce char(64) PRIMARY KEY,
  claimed_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT nonce_hex CHECK (nonce ~ '^[a-f0-9]{64}$')
);
CREATE TABLE IF NOT EXISTS level3_custody.approval_claim (
  nonce char(64) PRIMARY KEY,
  path text NOT NULL,
  payload_sha256 char(64) NOT NULL,
  state text NOT NULL CHECK (state IN ('claimed','complete')),
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  CONSTRAINT approved_path CHECK (
    path ~ '^(docs/level3-staging/[A-Za-z0-9_-]+[.]md|tests/level3-staging/[A-Za-z0-9_-]+[.]txt)$'
  ),
  CONSTRAINT approved_digest CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
  CONSTRAINT completion_consistency CHECK (
    (state='claimed' AND completed_at IS NULL) OR
    (state='complete' AND completed_at IS NOT NULL)
  )
);
CREATE TABLE IF NOT EXISTS level3_custody.audit_event (
  sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_id uuid NOT NULL UNIQUE,
  nonce char(64) NOT NULL,
  phase text NOT NULL CHECK (phase IN ('claimed','complete','recovered')),
  payload_sha256 char(64) NOT NULL,
  previous_hash char(64) NOT NULL,
  event_hash char(64) NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT event_digest CHECK (payload_sha256 ~ '^[a-f0-9]{64}$')
);
-- Database role permissions must be configured by a separate provisioning migration.
-- Hash-chain verification and independent external anchoring are not implemented by this schema.
COMMIT;
