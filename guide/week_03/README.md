# Week 3: Python, Git & Development Environment

**Month 1: Foundations | Days 13–18**

Python is the orchestration layer of ifinmail App — APIs, admin workflows, DNS verification, background tasks. This week builds solid Python fundamentals from zero, establishes Git discipline, and sets up the development environment we will use throughout the curriculum.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Write Python scripts using variables, data structures, functions, classes, and modules
- Use `venv` for isolated environments and `pip` for dependency management
- Use type hints and understand why ifinmail requires them
- Initialize Git repositories, make commits, branch, merge, and resolve conflicts
- Set up VS Code (or your editor) for Python development
- Write a small API endpoint using FastAPI

---

## Day 1 (Monday): Python Syntax & Data Structures

### Learning Objectives
- Run Python interactively (`python3` REPL) and as scripts
- Work with basic types: `str`, `int`, `float`, `bool`, `None`
- Use collections: `list`, `tuple`, `dict`, `set`
- Write list/dict comprehensions
- Handle strings and bytes (important for email parsing later)

### Theory / Reading
- **Python is dynamically typed** but we use type hints for safety
- **Lists vs tuples**: mutable vs immutable
- **Dictionaries**: key-value mappings; used everywhere in API responses
- **Bytes vs str**: email messages are bytes; APIs use strings

### Practical Exercise
```python
# ~/ifinmail-python/day01_basics.py

# --- Lists and dictionaries (core API response structures) ---
mailboxes = ["INBOX", "Sent", "Drafts", "Archive", "Trash"]

message = {
    "id": "msg_001",
    "from": "sender@trusted.org",
    "to": ["user@ifinmail.com"],
    "subject": "Welcome to ifinmail",
    "flags": ["\\Seen", "\\Answered"],
    "size_bytes": 2048,
}

# --- List comprehension ---
unread_messages = [
    {"id": f"msg_{i:03d}", "subject": f"Message {i}", "flags": flags}
    for i, flags in enumerate([["\\Seen"], [], ["\\Seen"], [], ["\\Flagged"]])
]
unread = [m for m in unread_messages if "\\Seen" not in m["flags"]]
print(f"Unread: {len(unread)} of {len(unread_messages)} messages")

# --- Dict comprehension ---
mailbox_counts = {m["id"]: len(m["subject"]) for m in unread_messages}
print(f"Subject lengths: {mailbox_counts}")

# --- String operations ---
raw_header = "From: Sender <sender@ifinmail.com>\r\nTo: user@trusted.org\r\nSubject: Hello\r\n"
headers = dict(line.split(": ", 1) for line in raw_header.strip().split("\r\n") if ": " in line)
print(f"Parsed headers: {headers}")

# --- Bytes handling (email messages are bytes on the wire) ---
email_bytes = b"Subject: Test\r\n\r\nHello, world!\r\n"
email_str = email_bytes.decode("utf-8")
print(f"Bytes length: {len(email_bytes)}, String length: {len(email_str)}")
```

### Checkpoint Questions
1. Why does email handling frequently involve converting between `bytes` and `str`?
2. What is the advantage of a `dict` for representing a message vs a `list`?
3. When would you use a `tuple` instead of a `list`?
4. How is a `set` useful when working with email flags?

### Connection to ifinmail App
Every API response in ifinmail will be JSON — Python lists and dicts map directly. Email messages arrive as bytes from Postfix and must be parsed. The Rust core will also use these concepts (though with stricter types).

---

## Day 2 (Tuesday): Functions, Modules & Virtual Environments

### Learning Objectives
- Write clean functions with parameters and return values
- Use `*args`, `**kwargs`, default arguments
- Organize code into modules and packages
- Create and use virtual environments with `venv`
- Install and pin dependencies with `pip`

### Theory / Reading
- **Functions**: `def name(param: type) -> ReturnType:`
- **Modules**: one `.py` file = one module; a folder with `__init__.py` = a package
- **venv**: isolated Python environment; never install project deps globally
- **pip freeze**: lock dependencies to exact versions (`requirements.txt` or `pyproject.toml`)

### Practical Exercise
```bash
# Create a virtual environment
mkdir -p ~/ifinmail-python
python3 -m venv ~/ifinmail-python/venv
source ~/ifinmail-python/venv/bin/activate  # Linux/macOS
# OR: ~/ifinmail-python/venv\Scripts\Activate.ps1 (Windows PowerShell)

# Verify isolation
which python3   # Should point inside venv/
which pip        # Should point inside venv/
```

```python
# ~/ifinmail-python/mail_utils/__init__.py
"""Mail utility functions for ifinmail — Week 3."""

from .headers import parse_email_headers
from .validation import is_valid_email_address

__all__ = ["parse_email_headers", "is_valid_email_address"]
```

```python
# ~/ifinmail-python/mail_utils/validation.py
import re

# RFC 5322 simplified — production code would use a proper parser
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

def is_valid_email_address(address: str) -> bool:
    """Check if an address looks like a valid email."""
    return bool(_EMAIL_RE.match(address))

# Quick tests
if __name__ == "__main__":
    tests = ["user@ifinmail.com", "not-an-email", "admin@localhost", ""]
    for t in tests:
        print(f"  {t:30s} → {is_valid_email_address(t)}")
```

```python
# ~/ifinmail-python/mail_utils/headers.py
from typing import Dict, List

def parse_email_headers(raw: str) -> Dict[str, str]:
    """Parse raw email headers into a dictionary."""
    headers = {}
    for line in raw.strip().split("\r\n"):
        if ": " in line:
            key, value = line.split(": ", 1)
            headers[key.lower()] = value
    return headers
```

### Checkpoint Questions
1. Why does ifinmail use virtual environments instead of installing packages globally?
2. What goes in `__init__.py`? What does `__all__` control?
3. How do type hints help in a multi-developer project like ifinmail?
4. What is the difference between `requirements.txt` and `pyproject.toml`?

### Connection to ifinmail App
The proposal requires "pinned dependencies and lockfiles" (Section 3.3). The Python API layer will be organized as packages: `ifinmail.api`, `ifinmail.admin`, `ifinmail.mail`, `ifinmail.auth`. Every function will use type hints for safety.

---

## Day 3 (Wednesday): Git Fundamentals

### Learning Objectives
- Initialize a Git repository and make commits
- Understand staging area, commits, branches, and remotes
- Write meaningful commit messages
- Collaborate using branches and merge/pull requests
- Read `git log` and `git diff` to understand project history

### Theory / Reading
- **Three states**: working directory → staging area → repository
- **Commits**: snapshots, not diffs; each has a SHA hash
- **Branches**: lightweight pointers; `main` is the default
- **Remote**: shared repository (GitHub, GitLab)

### Practical Exercise
```bash
# Initialize a practice repository
mkdir -p ~/ifinmail-git-practice
cd ~/ifinmail-git-practice
git init

# Configure identity (if not already done)
git config user.name "Your Name"
git config user.email "you@eleso.com"

# Create initial structure
mkdir -p {src,tests,docs}
echo "# ifinmail Practice Repo" > README.md
echo "__pycache__/" > .gitignore
echo "venv/" >> .gitignore
echo ".env" >> .gitignore

# Stage and commit
git add README.md .gitignore
git commit -m "Initial commit: project scaffold"

# Create a feature branch
git checkout -b feature/mail-parser

# Make changes on the branch
echo '"""Mail parsing module."""' > src/parser.py
echo '__version__ = "0.1.0"' >> src/parser.py
git add src/parser.py
git commit -m "Add mail parser module skeleton"

# View history
git log --oneline --graph --all

# Switch back and merge
git checkout main
git merge feature/mail-parser

# Practice conflict resolution
git checkout -b feature/update-parser
echo '__version__ = "0.2.0"' > src/parser.py
echo 'def parse_mime(): pass' >> src/parser.py
git add src/parser.py
git commit -m "Update parser version to 0.2.0"

git checkout main
echo '__version__ = "0.1.0"' > src/parser.py
echo 'def parse_headers(): pass' >> src/parser.py
git add src/parser.py
git commit -m "Add parse_headers function"

# Merge — this will create a conflict!
git merge feature/update-parser
# Resolve the conflict in src/parser.py, then:
# git add src/parser.py
# git commit -m "Merge feature/update-parser: resolve version conflict"

# Clean up
cd ~
```

### Checkpoint Questions
1. What is the purpose of `.gitignore`? What should ifinmail's `.gitignore` contain?
2. What makes a good commit message? Why does the proposal require "signed commits"?
3. When should you branch vs commit directly to main?
4. How does `git log --oneline --graph` help understand project history?

### Connection to ifinmail App
The proposal requires signed commits and signed releases (Section 3.3). ifinmail is hosted at `github.com/ifinsta/ifinmail`. Every week of this curriculum adds to a Git repository. Clean Git history is part of the project's supply-chain security.

---

## Day 4 (Thursday): Type Hints & Error Handling

### Learning Objectives
- Use Python type hints for function signatures and variables
- Understand `Optional`, `Union`, `Literal`, `TypedDict`
- Handle errors with `try`/`except`/`finally` and `raise`
- Write custom exception classes
- Run `mypy` for static type checking

### Theory / Reading
- **Type hints are documentation that tools can verify**
- **`mypy`**: static type checker; catches bugs before runtime
- **Errors vs exceptions**: Python uses exceptions for error handling
- **Structured errors**: ifinmail APIs must return consistent error shapes

### Practical Exercise
```bash
# Install mypy
source ~/ifinmail-python/venv/bin/activate
pip install mypy
```

```python
# ~/ifinmail-python/day04_typed.py
from typing import Optional, TypedDict, Literal
from dataclasses import dataclass

# --- TypedDict for API responses ---
class MailboxInfo(TypedDict):
    name: str
    total: int
    unread: int

class ApiError(Exception):
    """Structured error matching ifinmail API contract (Section 7.1)."""
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)

# --- Typed function ---
def get_mailbox_stats(mailbox: str, messages: list[dict]) -> MailboxInfo:
    """Calculate mailbox statistics."""
    if not messages:
        raise ApiError("EMPTY_MAILBOX", f"Mailbox '{mailbox}' has no messages")
    
    total = len(messages)
    unread = sum(1 for m in messages if "\\Seen" not in m.get("flags", []))
    
    return MailboxInfo(name=mailbox, total=total, unread=unread)

# --- Usage ---
messages = [
    {"id": "1", "flags": ["\\Seen"]},
    {"id": "2", "flags": []},
    {"id": "3", "flags": ["\\Seen", "\\Flagged"]},
    {"id": "4", "flags": []},
]

try:
    stats = get_mailbox_stats("INBOX", messages)
    print(f"INBOX: {stats['unread']} unread / {stats['total']} total")
    
    # This will raise
    get_mailbox_stats("EMPTY", [])
except ApiError as e:
    print(f"API Error [{e.code}]: {e.message} (HTTP {e.status})")

# Run: mypy day04_typed.py
```

### Checkpoint Questions
1. Why does ifinmail require type hints in all Python code?
2. What does `Optional[str]` mean? How is it different from `str`?
3. How do structured API errors (Section 7.1) help client developers?
4. What does `mypy` catch that Python's runtime does not?

### Connection to ifinmail App
Section 7.1 of the proposal mandates "structured and consistent" API errors. Type hints catch bugs in the API layer before they reach production. The integration between Python and Rust (via pyo3) relies on clear type boundaries.

---

## Day 5 (Friday): Introduction to FastAPI

### Learning Objectives
- Understand what ASGI/WSGI frameworks do
- Create a minimal FastAPI application
- Define Pydantic models for request/response validation
- Add route handlers with path parameters, query parameters, and bodies
- Auto-generate OpenAPI documentation

### Theory / Reading
- **FastAPI**: modern Python web framework built on Starlette and Pydantic
- **Pydantic**: data validation using Python type hints
- **OpenAPI/Swagger**: machine-readable API documentation
- **ASGI**: asynchronous server gateway interface (successor to WSGI)

### Practical Exercise
```bash
# Install FastAPI
source ~/ifinmail-python/venv/bin/activate
pip install fastapi uvicorn pydantic
```

```python
# ~/ifinmail-python/day05_api.py
"""
Minimal ifinmail Mail API — preview of the full API contract.
Run with: uvicorn day05_api:app --reload
Then visit: http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

app = FastAPI(
    title="ifinmail API (Training)",
    version="0.1.0",
    description="Preview of the ifinmail Mail API contract — Week 3",
)

# --- Pydantic Models (matches proposal Section 11 entities) ---
class Message(BaseModel):
    id: str
    from_: str  # aliased to 'from' in JSON
    to: List[str]
    subject: str
    body_text: str
    flags: List[str] = []
    created_at: datetime = datetime.now()

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "msg_001",
                "from_": "sender@ifinmail.com",
                "to": ["user@ifinmail.com"],
                "subject": "Welcome!",
                "body_text": "Hello from ifinmail.",
                "flags": ["\\Seen"],
            }
        }

class SendMessageRequest(BaseModel):
    to: List[str]
    subject: str
    body_text: str

class ApiErrorResponse(BaseModel):
    code: str
    message: str
    status: int

# --- In-memory "database" (Week 4 will use real PostgreSQL) ---
inbox: List[Message] = [
    Message(id="msg_001", from_="admin@ifinmail.com", to=["trainee@ifinmail.com"],
            subject="Welcome to ifinmail", body_text="Let's build an email platform!", flags=["\\Seen"]),
    Message(id="msg_002", from_="sender@trusted.org", to=["trainee@ifinmail.com"],
            subject="Your first message", body_text="This is a sample message.", flags=[]),
]

# --- Routes (matching proposal Section 7.2 Mail API) ---
@app.get("/v1/mailboxes")
async def list_mailboxes():
    """List available mailboxes (Section 7.2 Mail API)."""
    return {"mailboxes": ["INBOX", "Sent", "Drafts", "Archive", "Trash"]}

@app.get("/v1/mail/messages")
async def list_messages(
    mailbox: str = Query("INBOX", description="Mailbox name"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List messages in a mailbox."""
    return {
        "mailbox": mailbox,
        "total": len(inbox),
        "limit": limit,
        "offset": offset,
        "messages": inbox[offset:offset + limit],
    }

@app.get("/v1/mail/messages/{message_id}")
async def read_message(message_id: str):
    """Read a single message by ID."""
    for msg in inbox:
        if msg.id == message_id:
            return msg
    raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Message {message_id} not found"})

@app.post("/v1/mail/messages")
async def send_message(req: SendMessageRequest):
    """Send a new message (enqueue for delivery)."""
    new_msg = Message(
        id=f"msg_{len(inbox)+1:03d}",
        from_="trainee@ifinmail.com",
        to=req.to,
        subject=req.subject,
        body_text=req.body_text,
    )
    inbox.append(new_msg)
    return {"status": "queued", "message": new_msg}

@app.get("/v1/health")
async def health_check():
    return {"status": "ok", "service": "ifinmail-api"}

# Run: uvicorn day05_api:app --reload --host 0.0.0.0 --port 8000
```

### Checkpoint Questions
1. What does Pydantic do that plain Python dicts cannot?
2. Where does the OpenAPI schema appear when you run this app?
3. How does this API structure map to the proposal's API groups (Section 7.2)?
4. Why use `from_` instead of `from` in the Pydantic model?

### Connection to ifinmail App
This FastAPI app is a miniature version of the ifinmail API layer. The real API will have Auth, Admin, Device Bootstrap, and WebSocket groups instead of just Mail. But the patterns — Pydantic models, structured errors, versioned endpoints — are identical.

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: Build a Mailbox CLI Client

Write a Python script `~/ifinmail-python/mail_cli.py` that:

1. Connects to the Day 5 FastAPI server (or works with local state)
2. Lists mailboxes
3. Lists messages in a mailbox
4. Reads a specific message by ID
5. "Sends" a message (posts to the API)
6. Uses type hints throughout
7. Handles API errors gracefully

**Stretch goal**: Add a `--search` flag that filters messages by subject substring.

### Week 3 Self-Assessment

Before moving to Week 4, confirm you can:
- [ ] Write Python functions with type hints and docstrings
- [ ] Create and activate a virtual environment
- [ ] Import from modules and packages you created
- [ ] Initialize a Git repo, branch, commit, and merge
- [ ] Write and run a FastAPI application with multiple routes
- [ ] Define Pydantic models that match the ifinmail data model
- [ ] Run `mypy` and fix type errors

---

## Week 3 Resource Index

| Resource | Location |
|---|---|
| Python cheat sheet | `references/python_cheatsheet.md` |
| Git workflow guide | `references/git_workflow.md` |
| FastAPI/Pydantic reference | `references/fastapi_basics.md` |
| Day 5 API code | `code/day05_api.py` |
| Day 6 CLI challenge | `challenges/week_03_mail_cli.md` |

---

*Week 3 of 12 — Python, Git & Development Environment for ifinmail Platform Engineering*
