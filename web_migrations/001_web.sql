CREATE TABLE web_users (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 username varchar(48) NOT NULL,
 password_hash text NOT NULL,
 role text NOT NULL CHECK(role IN ('admin','viewer')),
 active boolean NOT NULL DEFAULT true,
 must_change_password boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now(),
 last_login timestamptz
);
CREATE UNIQUE INDEX web_users_username_idx ON web_users(lower(username));
CREATE TABLE web_sessions (
 token_hash text PRIMARY KEY,
 user_id bigint NOT NULL REFERENCES web_users(id) ON DELETE CASCADE,
 expires_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX web_sessions_expiry_idx ON web_sessions(expires_at);
CREATE TABLE web_clients (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name varchar(80) NOT NULL,
 source_ip inet NOT NULL UNIQUE,
 enabled boolean NOT NULL DEFAULT true,
 ssh_port integer NOT NULL DEFAULT 22 CHECK(ssh_port BETWEEN 1 AND 65535),
 ssh_username varchar(64) NOT NULL DEFAULT '',
 host_fingerprint text NOT NULL DEFAULT '',
 action_name varchar(32) NOT NULL DEFAULT 'logsaiPrivate',
 notes varchar(300) NOT NULL DEFAULT '',
 last_apply_status text,
 last_applied_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE VIEW web_client_sources AS SELECT host(source_ip) AS source_ip, enabled FROM web_clients;
CREATE TABLE web_login_limits (
 key text PRIMARY KEY,
 failures integer NOT NULL,
 window_start timestamptz NOT NULL
);
CREATE TABLE web_audit_log (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 user_id bigint REFERENCES web_users(id),
 action text NOT NULL,
 target_id bigint,
 created_at timestamptz NOT NULL DEFAULT now()
);
