CREATE_DOMAINS = """
CREATE TABLE IF NOT EXISTS domains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain      TEXT    NOT NULL UNIQUE,
    verified    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    email               TEXT    NOT NULL UNIQUE,
    password            TEXT    NOT NULL,
    domain_id           INTEGER NOT NULL,
    is_admin            INTEGER NOT NULL DEFAULT 0,
    first_name          TEXT,
    last_name           TEXT,
    last_login          TEXT,
    storage_limit       INTEGER NOT NULL DEFAULT 0,
    quota_warning_sent  INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE
);
"""

CREATE_MAILBOXES = """
CREATE TABLE IF NOT EXISTS mailboxes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL UNIQUE,
    user_id     INTEGER NOT NULL,
    quota_mb    INTEGER NOT NULL DEFAULT 1024,
    used_mb     INTEGER NOT NULL DEFAULT 0,
    enabled     INTEGER NOT NULL DEFAULT 1,
    plan        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

CREATE_ALIASES = """
CREATE TABLE IF NOT EXISTS aliases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL UNIQUE,
    target      TEXT    NOT NULL,
    domain_id   INTEGER NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE
);
"""

CREATE_SECURITY_EVENTS = """
CREATE TABLE IF NOT EXISTS security_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT    NOT NULL,
    description     TEXT,
    ip_address      TEXT,
    user_id         INTEGER,
    metadata_json   TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
"""

CREATE_BACKUPS = """
CREATE TABLE IF NOT EXISTS backups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL,
    size_bytes  INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'pending',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

SCHEMA = [CREATE_DOMAINS, CREATE_USERS, CREATE_MAILBOXES, CREATE_ALIASES, CREATE_SECURITY_EVENTS, CREATE_BACKUPS]
