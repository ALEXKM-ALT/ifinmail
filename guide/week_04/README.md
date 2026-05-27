# Week 4: Databases & Data Modeling

**Month 1: Foundations | Days 19–24**

PostgreSQL and Redis are the data backbone of ifinmail App. PostgreSQL holds users, domains, mail metadata, and audit logs. Redis handles queues, rate limits, counters, and ephemeral state. This week covers SQL fundamentals, schema design, and the ifinmail data model.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Install and configure PostgreSQL and Redis
- Write SQL queries: SELECT, INSERT, UPDATE, DELETE, JOIN, subqueries
- Design normalized database schemas
- Map the ifinmail proposal entities to tables and relationships
- Use Redis for caching, counters, and rate limiting
- Connect Python to PostgreSQL and Redis

---

## Day 1 (Monday): PostgreSQL Installation & First Queries

### Learning Objectives
- Install PostgreSQL and create a database
- Understand the psql command-line client
- Create tables with constraints
- Run basic CRUD queries
- Understand PostgreSQL's role vs MySQL and SQLite

### Theory / Reading
- **PostgreSQL**: open-source relational database, ACID-compliant, JSON support, full-text search
- **psql**: the PostgreSQL interactive terminal
- **Schemas**: namespaces within a database (we will use `ifinmail`)
- **Constraints**: PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL, CHECK

### Practical Exercise
```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt update && sudo apt install -y postgresql postgresql-client

# Start and enable
sudo systemctl start postgresql
sudo systemctl enable postgresql
sudo systemctl status postgresql

# Access PostgreSQL as the postgres superuser
sudo -u postgres psql
```

```sql
-- Inside psql: create the ifinmail database and schema
CREATE DATABASE ifinmail;
\c ifinmail

CREATE SCHEMA IF NOT EXISTS ifinmail;

-- Create a practice table: organizations (matches proposal Section 11)
CREATE TABLE ifinmail.organizations (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(64) NOT NULL UNIQUE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create a related table: domains
CREATE TABLE ifinmail.domains (
    id              SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES ifinmail.organizations(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL UNIQUE,
    verified        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert test data
INSERT INTO ifinmail.organizations (name, slug) VALUES
    ('Eleso Solution', 'eleso'),
    ('Acme Corp', 'acme');

INSERT INTO ifinmail.domains (organization_id, name, verified) VALUES
    (1, 'eleso.com', TRUE),
    (1, 'ifinsta.io', FALSE),
    (2, 'acme.com', TRUE);

-- Query with JOIN
SELECT o.name AS org, d.name AS domain, d.verified
FROM ifinmail.organizations o
JOIN ifinmail.domains d ON d.organization_id = o.id
ORDER BY o.name, d.name;

-- Filtering
SELECT * FROM ifinmail.domains WHERE verified = FALSE;
SELECT * FROM ifinmail.domains WHERE name LIKE '%.com';

-- Aggregation
SELECT o.name, COUNT(d.id) AS domain_count
FROM ifinmail.organizations o
LEFT JOIN ifinmail.domains d ON d.organization_id = o.id
GROUP BY o.name;

-- Clean up practice data
-- DROP TABLE ifinmail.domains CASCADE;
-- DROP TABLE ifinmail.organizations CASCADE;
```

### Checkpoint Questions
1. Why does ifinmail use PostgreSQL instead of MySQL or SQLite?
2. What does `ON DELETE CASCADE` do? Why is it important for domains?
3. Why do we use a separate `ifinmail` schema instead of the default `public`?
4. What is the difference between `TIMESTAMP` and `TIMESTAMP WITH TIME ZONE`? Which does ifinmail need?

### Connection to ifinmail App
PostgreSQL is the "system of record" (Section 10.3). Every entity in Section 11 of the proposal maps to PostgreSQL tables. This week's schema exercises build directly toward the production data model.

---

## Day 2 (Tuesday): Advanced SQL & Data Modeling

### Learning Objectives
- Write multi-table JOINs (INNER, LEFT, RIGHT)
- Use subqueries and CTEs (Common Table Expressions)
- Create indexes for query performance
- Understand transactions and ACID guarantees
- Begin mapping ifinmail entities to tables

### Theory / Reading
- **Normalization**: eliminate redundancy; 3NF is the practical target
- **Indexes**: speed up reads, slow down writes; index columns used in WHERE/JOIN
- **Transactions**: atomic units of work; COMMIT or ROLLBACK
- **CTEs**: `WITH name AS (SELECT ...) SELECT ... FROM name` — cleaner than nested subqueries

### Practical Exercise
```sql
-- Create the full ifinmail core data model (preview of production schema)
CREATE TABLE ifinmail.users (
    id              SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES ifinmail.organizations(id),
    username        VARCHAR(255) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    trust_level     INTEGER DEFAULT 0 CHECK (trust_level BETWEEN 0 AND 4),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE ifinmail.mailboxes (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES ifinmail.users(id) ON DELETE CASCADE,
    domain_id   INTEGER NOT NULL REFERENCES ifinmail.domains(id),
    local_part  VARCHAR(64) NOT NULL,  -- part before @
    quota_mb    INTEGER DEFAULT 1000,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(domain_id, local_part)
);

CREATE TABLE ifinmail.aliases (
    id          SERIAL PRIMARY KEY,
    domain_id   INTEGER NOT NULL REFERENCES ifinmail.domains(id),
    source      VARCHAR(64) NOT NULL,
    destination VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE ifinmail.devices (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES ifinmail.users(id) ON DELETE CASCADE,
    device_name VARCHAR(255),
    platform    VARCHAR(32),  -- android, windows, macos, linux, web
    public_key  TEXT,
    approved    BOOLEAN DEFAULT FALSE,
    last_seen   TIMESTAMP WITH TIME ZONE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX idx_mailboxes_user ON ifinmail.mailboxes(user_id);
CREATE INDEX idx_mailboxes_domain_local ON ifinmail.mailboxes(domain_id, local_part);
CREATE INDEX idx_devices_user ON ifinmail.devices(user_id);
CREATE INDEX idx_users_email ON ifinmail.users(email);

-- Insert sample data
INSERT INTO ifinmail.users (organization_id, username, email, password_hash, trust_level) VALUES
    (1, 'alice', 'alice@eleso.com', '$argon2id$hash_placeholder', 2),
    (1, 'bob', 'bob@eleso.com', '$argon2id$hash_placeholder', 1),
    (2, 'carol', 'carol@acme.com', '$argon2id$hash_placeholder', 3);

INSERT INTO ifinmail.mailboxes (user_id, domain_id, local_part) VALUES
    (1, 1, 'alice'),
    (2, 1, 'bob'),
    (3, 2, 'carol');

-- CTE example: find users with unverified domains
WITH unverified AS (
    SELECT id, name FROM ifinmail.domains WHERE verified = FALSE
)
SELECT u.username, u.email, d.name AS domain
FROM ifinmail.users u
JOIN unverified d ON u.organization_id = d.id;

-- Transaction example
BEGIN;
    UPDATE ifinmail.users SET trust_level = 2 WHERE email = 'bob@eleso.com';
    -- If something fails here, ROLLBACK undoes the UPDATE
    SELECT * FROM ifinmail.users WHERE email = 'bob@eleso.com';
COMMIT;
```

### Checkpoint Questions
1. Why is `UNIQUE(domain_id, local_part)` important for the mailboxes table?
2. What is the purpose of the `trust_level` CHECK constraint?
3. How do indexes help the ifinmail API respond faster?
4. Why would you use a CTE instead of a subquery?

### Connection to ifinmail App
Every entity from Section 11 of the proposal (Organization, Domain, User, Mailbox, Alias, Device, Session, API Key, etc.) will become PostgreSQL tables with proper constraints, indexes, and relationships. This exercise is the foundation of the production schema.

---

## Day 3 (Wednesday): PostgreSQL Full-Text Search

### Learning Objectives
- Understand PostgreSQL FTS concepts: tsvector, tsquery, GIN indexes
- Implement basic email search by subject and body
- Rank search results with `ts_rank`
- Understand the limits of PostgreSQL FTS for email scale

### Theory / Reading
- **tsvector**: preprocessed document for searching (stemmed, normalized tokens)
- **tsquery**: search query with boolean operators (`&`, `|`, `!`)
- **GIN index**: Generalized Inverted Index — makes FTS fast
- **Proposal Section 12**: "Initial implementation may use PostgreSQL full-text search"

### Practical Exercise
```sql
-- Create a messages_meta table for search practice
CREATE TABLE ifinmail.messages_meta (
    id          SERIAL PRIMARY KEY,
    mailbox_id  INTEGER NOT NULL REFERENCES ifinmail.mailboxes(id) ON DELETE CASCADE,
    message_id  VARCHAR(64) NOT NULL,
    sender      VARCHAR(255),
    subject     VARCHAR(512),
    body_text   TEXT,
    flags       TEXT[] DEFAULT '{}',
    received_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create a tsvector column and GIN index
ALTER TABLE ifinmail.messages_meta ADD COLUMN search_vector tsvector;
CREATE INDEX idx_messages_search ON ifinmail.messages_meta USING GIN(search_vector);

-- Populate search vector from subject and body
UPDATE ifinmail.messages_meta
SET search_vector = 
    setweight(to_tsvector('english', COALESCE(subject, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(body_text, '')), 'B');

-- Insert sample messages
INSERT INTO ifinmail.messages_meta (mailbox_id, message_id, sender, subject, body_text, flags)
VALUES
    (1, 'abc001', 'admin@ifinsta.io', 'Welcome to ifinmail', 'This is the welcome message for new users.', '{"\\Seen"}'),
    (1, 'abc002', 'bob@eleso.com', 'Meeting tomorrow', 'Let us discuss the deployment plan for Phase 1.', '{}'),
    (1, 'abc003', 'noreply@acme.com', 'Invoice for March', 'Your invoice amount is $500. Please review.', '{"\\Flagged"}'),
    (2, 'abc004', 'carol@acme.com', 'Postfix configuration', 'Can you review the main.cf changes before we apply them?', '{"\\Seen"}'),
    (2, 'abc005', 'admin@ifinsta.io', 'Security alert: new device', 'A new device was registered for your account.', '{}');

-- Refresh search vectors
UPDATE ifinmail.messages_meta
SET search_vector = 
    setweight(to_tsvector('english', COALESCE(subject, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(body_text, '')), 'B');

-- --- Search queries ---

-- Simple search
SELECT id, sender, subject, ts_rank(search_vector, query) AS rank
FROM ifinmail.messages_meta, plainto_tsquery('english', 'welcome message') query
WHERE search_vector @@ query
ORDER BY rank DESC;

-- Boolean search
SELECT id, subject
FROM ifinmail.messages_meta
WHERE search_vector @@ to_tsquery('english', 'postfix & configuration');

-- Search with filters (matching Section 12: sender, subject, date range, folder, read/unread)
SELECT id, sender, subject, received_at
FROM ifinmail.messages_meta
WHERE search_vector @@ plainto_tsquery('english', 'deployment')
  AND '{\\Seen}'::text[] && flags   -- has \Seen flag
ORDER BY received_at DESC;

-- Phrase search
SELECT id, subject
FROM ifinmail.messages_meta
WHERE search_vector @@ phraseto_tsquery('english', 'deployment plan');
```

### Checkpoint Questions
1. What does `setweight('A')` vs `setweight('B')` do? Why weight subject higher?
2. What are the limitations of PostgreSQL FTS for a mail system at scale?
3. How does a GIN index make search faster?
4. When would ifinmail need a dedicated search engine instead?

### Connection to ifinmail App
Section 12 of the proposal explicitly plans PostgreSQL FTS as the initial search implementation. Every official client's search bar will query these indexes. Understanding FTS now means you can build the search feature from day one.

---

## Day 4 (Thursday): Redis — Queues, Caches & Rate Limits

### Learning Objectives
- Install Redis and use redis-cli
- Understand Redis data types: strings, hashes, lists, sets, sorted sets
- Implement a rate limiter using Redis
- Use Redis as a task queue
- Understand Redis persistence (RDB vs AOF)

### Theory / Reading
- **Redis**: in-memory data structure store; sub-millisecond latency
- **Use cases in ifinmail**: rate limits, session tokens, verification codes, task queues, event counters
- **Key naming convention**: `ifinmail:<entity>:<id>:<field>`
- **TTL**: time-to-live for automatic key expiration (perfect for rate limits)

### Practical Exercise
```bash
# Install Redis
sudo apt update && sudo apt install -y redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server

# Connect
redis-cli
```

```redis
# In redis-cli:

# --- Strings (sessions, tokens, counters) ---
SET ifinmail:user:1:session "eyJhbGciOi..." EX 1800
GET ifinmail:user:1:session
TTL ifinmail:user:1:session

INCR ifinmail:stats:messages_sent
INCR ifinmail:stats:messages_sent
GET ifinmail:stats:messages_sent

# --- Hashes (user profiles, config) ---
HSET ifinmail:user:1 username "alice" email "alice@eleso.com" trust_level 2
HGET ifinmail:user:1 email
HGETALL ifinmail:user:1

# --- Lists (task queues) ---
LPUSH ifinmail:queue:outbound '{"to":"bob@eleso.com","subject":"Hello"}'
LPUSH ifinmail:queue:outbound '{"to":"carol@acme.com","subject":"Meeting"}'
LLEN ifinmail:queue:outbound
RPOP ifinmail:queue:outbound   # Dequeue the oldest

# --- Sorted Sets (rate limit windows) ---
# Track sending timestamps per user
ZADD ifinmail:sent:user:1 $(date +%s) "msg_001"
ZADD ifinmail:sent:user:1 $(date +%s) "msg_002"
ZCOUNT ifinmail:sent:user:1 $(($(date +%s) - 3600)) $(date +%s)  # Messages in last hour

# --- Rate Limiter Logic (simplified) ---
# Count sends in the last hour for user 1
ZREMRANGEBYSCORE ifinmail:sent:user:1 0 $(($(date +%s) - 3600))  # Clean old entries
ZCOUNT ifinmail:sent:user:1 $(($(date +%s) - 3600)) $(date +%s)
# If count > limit, reject

# --- Expire keys automatically ---
SET ifinmail:ratelimit:user:1:send 0 EX 3600
INCR ifinmail:ratelimit:user:1:send
TTL ifinmail:ratelimit:user:1:send

# Clean up practice keys
KEYS ifinmail:*
# FLUSHDB  # WARNING: deletes all keys in current DB
```

### Checkpoint Questions
1. Why use Redis for rate limiting instead of PostgreSQL?
2. What does `EX 1800` do in the `SET` command? Why is TTL important?
3. How would you implement the proposal's "trust level" sending limits using Redis sorted sets?
4. What is the difference between Redis lists (queues) and sorted sets (rate windows)?

### Connection to ifinmail App
Section 6.2 defines trust-based sending limits. Redis is the engine that enforces them in real time. The proposal lists Redis for "queues, rate limits, policy counters, and temporary verification flows" — every Redis data type maps to a specific ifinmail feature.

---

## Day 5 (Friday): Python ↔ Database Integration

### Learning Objectives
- Connect Python to PostgreSQL using `psycopg2` or `asyncpg`
- Connect Python to Redis using `redis-py`
- Write a data access layer for the ifinmail mail API
- Replace the Day 5 in-memory store from Week 3 with real database queries

### Theory / Reading
- **psycopg2**: synchronous PostgreSQL driver; mature and stable
- **asyncpg**: asynchronous PostgreSQL driver; higher performance
- **redis-py**: official Redis client for Python
- **Connection pooling**: reuse connections instead of opening new ones per request

### Practical Exercise
```bash
# Install Python database drivers
source ~/ifinmail-python/venv/bin/activate
pip install psycopg2-binary redis fastapi uvicorn
```

```python
# ~/ifinmail-python/day05_database.py
"""
Database layer for ifinmail API — connects Week 3 API patterns with Week 4 databases.
"""
import redis
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

# --- PostgreSQL Connection ---
DB_CONFIG = {
    "dbname": "ifinmail",
    "user": "ifinmail",
    "password": "changeme",  # In production: use env vars / secrets manager
    "host": "localhost",
    "port": 5432,
}

@contextmanager
def get_db():
    """Yield a database connection with automatic cleanup."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()

# --- Redis Connection ---
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

# --- Data Access Functions ---
def list_mailboxes(user_id: int) -> List[Dict[str, Any]]:
    """Fetch mailboxes for a user from PostgreSQL."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, local_part, quota_mb, created_at FROM ifinmail.mailboxes WHERE user_id = %s",
                (user_id,),
            )
            return cur.fetchall()

def get_message_count(mailbox_id: int) -> int:
    """Count messages in a mailbox."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM ifinmail.messages_meta WHERE mailbox_id = %s",
                (mailbox_id,),
            )
            return cur.fetchone()[0]

def search_messages(mailbox_id: int, query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Full-text search using PostgreSQL FTS."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, message_id, sender, subject, body_text, received_at,
                       ts_rank(search_vector, plainto_tsquery('english', %s)) AS rank
                FROM ifinmail.messages_meta
                WHERE mailbox_id = %s AND search_vector @@ plainto_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                (query, mailbox_id, query, limit),
            )
            return cur.fetchall()

# --- Rate Limiter using Redis ---
def check_send_rate(user_id: int, max_per_hour: int = 100) -> bool:
    """
    Check if user is within their hourly send limit.
    Returns True if allowed, False if rate-limited.
    
    Matches proposal Section 6.2: trust-based sending limits.
    """
    key = f"ifinmail:ratelimit:user:{user_id}:send"
    count = redis_client.get(key)
    
    if count is None:
        redis_client.setex(key, 3600, 1)
        return True
    
    count = int(count)
    if count >= max_per_hour:
        return False
    
    redis_client.incr(key)
    return True

# --- Quick Test ---
if __name__ == "__main__":
    # Test Redis rate limiter
    print("Rate limit check (should pass):", check_send_rate(1, max_per_hour=100))
    redis_client.delete("ifinmail:ratelimit:user:1:send")  # Clean up
    
    # Test PostgreSQL queries
    print("Mailboxes for user 1:")
    try:
        for mb in list_mailboxes(1):
            count = get_message_count(mb["id"])
            print(f"  {mb['local_part']} — {count} messages")
    except Exception as e:
        print(f"  Database query failed: {e}")
        print("  (Run Day 1-3 exercises first to populate the database)")
```

### Checkpoint Questions
1. Why use a context manager (`with get_db()`) for database connections?
2. What does `RealDictCursor` provide that the default cursor does not?
3. How does the Redis rate limiter reset after one hour?
4. Why is `decode_responses=True` useful in the Redis client?

### Connection to ifinmail App
This is the bridge between Week 3's API layer and Week 4's data layer. The production ifinmail API will use these exact patterns: psycopg2 for PostgreSQL queries, redis-py for rate limits and sessions, and FastAPI to expose it all to clients.

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: Wire the API to the Database

Take the FastAPI app from Week 3 Day 5 and:
1. Replace the in-memory `inbox` list with PostgreSQL queries against `ifinmail.messages_meta`
2. Add rate limiting to the `POST /v1/mail/messages` endpoint using Redis
3. Add a `GET /v1/mail/search?q=...` endpoint using PostgreSQL FTS
4. Add proper error handling for database connection failures

**Stretch goal**: Add pagination using `LIMIT`/`OFFSET` that reads from the query string.

### Week 4 Self-Assessment

Before moving to Week 5, confirm you can:
- [ ] Create PostgreSQL tables with constraints, indexes, and relationships
- [ ] Write JOIN queries across 3+ tables
- [ ] Implement full-text search using tsvector and GIN indexes
- [ ] Use Redis for counters, rate limiting, and TTL-based expiry
- [ ] Connect Python to PostgreSQL and Redis with proper connection handling
- [ ] Map the ifinmail proposal entities to a normalized schema
- [ ] Explain transactions and when to use them

---

## Week 4 Resource Index

| Resource | Location |
|---|---|
| PostgreSQL setup guide | `references/postgresql_setup.md` |
| SQL cheat sheet | `references/sql_cheatsheet.md` |
| Redis commands reference | `references/redis_commands.md` |
| FTS sample data | `data/seed_messages.sql` |
| Day 6 challenge | `challenges/week_04_api_database.md` |

---

## Month 1 Completion Checklist

Congratulations — you have completed the Foundations month. Before entering Month 2, verify:

- [ ] **Linux**: Navigate, manage files/permissions/processes, write shell scripts, parse logs
- [ ] **Networking**: TCP/IP, DNS, SMTP, IMAP, TLS — know the protocols and ports
- [ ] **Python**: Functions, modules, type hints, venv, FastAPI, Pydantic
- [ ] **Git**: Init, clone, branch, commit, merge, resolve conflicts
- [ ] **Databases**: PostgreSQL schema design, SQL queries, FTS, Redis data structures
- [ ] **Integration**: Connect Python to databases, build API endpoints backed by real data

You are now ready to build the mail stack in Month 2.

---

*Week 4 of 12 — Databases & Data Modeling for ifinmail Platform Engineering*
