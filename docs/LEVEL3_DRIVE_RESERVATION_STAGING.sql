-- Staging-only proposal. DO NOT apply to production or broker roles.
-- The unique key serialises custody-object reservations in PostgreSQL.
-- It does not provide atomicity across PostgreSQL and Google Drive.
CREATE TABLE IF NOT EXISTS level3_custody.drive_upload_reservation (
    parent_id text NOT NULL CHECK (length(parent_id) BETWEEN 1 AND 256),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    owner_token text NOT NULL CHECK (owner_token ~ '^[0-9a-f]{32}$'),
    state text NOT NULL CHECK (state IN ('reserved', 'verified')),
    file_id text CHECK (file_id IS NULL OR length(file_id) BETWEEN 1 AND 256),
    created_at timestamptz NOT NULL DEFAULT now(),
    verified_at timestamptz,
    PRIMARY KEY (parent_id, sha256),
    CHECK ((state = 'reserved' AND file_id IS NULL AND verified_at IS NULL)
        OR (state = 'verified' AND file_id IS NOT NULL AND verified_at IS NOT NULL))
);
-- Explicitly remove inherited/default SELECT grants on this sensitive table.
-- The reservation owner token must not be visible to broker/auditor logins.
REVOKE SELECT ON TABLE level3_custody.drive_upload_reservation
    FROM level3_broker_login, level3_auditor_login;
-- No GRANT statements: a separately reviewed uploader identity is required.
