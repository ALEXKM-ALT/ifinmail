import argparse

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def register_user_subcommands(sub) -> None:
    p = sub.add_parser("user", help="Manage users")
    p_sub = p.add_subparsers(dest="action")
    p_sub.required = True

    p_add = p_sub.add_parser("add", help="Create a new user")
    p_add.add_argument("email", help="Email address")
    p_add.add_argument("--password", "-p", help="Password (prompt if omitted)")
    p_add.add_argument(
        "--domain",
        "-d",
        default=None,
        help="Domain (extracted from email if omitted)",
    )
    p_add.set_defaults(fn=cmd_user_add)

    p_list = p_sub.add_parser("list", help="List all users")
    p_list.add_argument("--domain", "-d", default=None, help="Filter by domain")
    p_list.set_defaults(fn=cmd_user_list)

    p_rm = p_sub.add_parser("remove", help="Remove a user")
    p_rm.add_argument("email", help="Email address")
    p_rm.set_defaults(fn=cmd_user_remove)

    p_pw = p_sub.add_parser("password", help="Set or reset a user's password")
    p_pw.add_argument("email", help="Email address")
    p_pw.add_argument("--password", "-p", help="New password (prompt if omitted)")
    p_pw.set_defaults(fn=cmd_user_password)


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _prompt_password() -> str:
    import getpass

    while True:
        p1 = getpass.getpass("Password: ")
        p2 = getpass.getpass("Confirm: ")
        if p1 == p2:
            return p1
        print("Passwords do not match. Try again.")


def _ensure_domain(email: str, domain_arg: str | None, conn) -> str:
    domain_part = email.split("@", 1)[-1] if "@" in email else domain_arg
    if not domain_part:
        print("Could not determine domain.", file=__import__("sys").stderr)
        __import__("sys").exit(1)
    row = conn.execute("SELECT id FROM domains WHERE domain = ?", (domain_part,)).fetchone()
    if not row:
        print(f"Domain '{domain_part}' not found. Register it first.", file=__import__("sys").stderr)
        __import__("sys").exit(1)
    return domain_part


def cmd_user_add(args: argparse.Namespace, conn) -> None:
    email = args.email.lower().strip()
    domain_name = _ensure_domain(email, args.domain, conn)
    password = args.password or _prompt_password()
    if len(password) < 6:
        print("Password must be at least 6 characters.", file=__import__("sys").stderr)
        __import__("sys").exit(1)
    pw_hash = _hash_password(password)
    domain_id = conn.execute("SELECT id FROM domains WHERE domain = ?", (domain_name,)).fetchone()["id"]
    try:
        conn.execute(
            "INSERT INTO users (email, password, domain_id) VALUES (?, ?, ?)",
            (email, pw_hash, domain_id),
        )
        conn.commit()
        print(f"User '{email}' created.")
    except Exception as e:
        print(f"Error: {e}", file=__import__("sys").stderr)
        __import__("sys").exit(1)


def cmd_user_list(args: argparse.Namespace, conn) -> None:
    if args.domain:
        rows = conn.execute(
            """SELECT u.id, u.email, u.is_admin, u.created_at
               FROM users u JOIN domains d ON u.domain_id = d.id
               WHERE d.domain = ? ORDER BY u.email""",
            (args.domain.lower().strip(),),
        ).fetchall()
    else:
        rows = conn.execute("SELECT id, email, is_admin, created_at FROM users ORDER BY email").fetchall()
    if not rows:
        print("No users found.")
        return
    print(f"{'ID':<4} {'Email':<40} {'Admin':<6} {'Created':<20}")
    print("-" * 70)
    for r in rows:
        admin = "yes" if r["is_admin"] else "no"
        print(f"{r['id']:<4} {r['email']:<40} {admin:<6} {r['created_at']:<20}")


def cmd_user_remove(args: argparse.Namespace, conn) -> None:
    email = args.email.lower().strip()
    cur = conn.execute("DELETE FROM users WHERE email = ?", (email,))
    conn.commit()
    if cur.rowcount:
        print(f"User '{email}' removed.")
    else:
        print(f"User '{email}' not found.", file=__import__("sys").stderr)
        __import__("sys").exit(1)


def cmd_user_password(args: argparse.Namespace, conn) -> None:
    email = args.email.lower().strip()
    password = args.password or _prompt_password()
    if len(password) < 6:
        print("Password must be at least 6 characters.", file=__import__("sys").stderr)
        __import__("sys").exit(1)
    pw_hash = _hash_password(password)
    cur = conn.execute(
        "UPDATE users SET password = ?, updated_at = datetime('now') WHERE email = ?",
        (pw_hash, email),
    )
    conn.commit()
    if cur.rowcount:
        print(f"Password updated for '{email}'.")
    else:
        print(f"User '{email}' not found.", file=__import__("sys").stderr)
        __import__("sys").exit(1)
