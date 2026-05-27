import argparse


def register_mailbox_subcommands(sub) -> None:
    p = sub.add_parser("mailbox", aliases=["mb"], help="Manage mailboxes")
    p_sub = p.add_subparsers(dest="action")
    p_sub.required = True

    p_create = p_sub.add_parser("create", help="Create a mailbox for a user")
    p_create.add_argument("email", help="User email address")
    p_create.add_argument("--quota", "-q", type=int, default=1024, help="Quota in MB")
    p_create.set_defaults(fn=cmd_mailbox_create)

    p_list = p_sub.add_parser("list", help="List mailboxes")
    p_list.add_argument("--domain", "-d", default=None, help="Filter by domain")
    p_list.set_defaults(fn=cmd_mailbox_list)

    p_delete = p_sub.add_parser("delete", help="Delete a mailbox")
    p_delete.add_argument("email", help="Email address")
    p_delete.set_defaults(fn=cmd_mailbox_delete)


def cmd_mailbox_create(args: argparse.Namespace, conn) -> None:
    email = args.email.lower().strip()
    user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        print(f"User '{email}' not found. Create the user first.", file=__import__("sys").stderr)
        __import__("sys").exit(1)
    try:
        conn.execute(
            "INSERT INTO mailboxes (email, user_id, quota_mb) VALUES (?, ?, ?)",
            (email, user["id"], args.quota),
        )
        conn.commit()
        print(f"Mailbox '{email}' created (quota: {args.quota} MB).")
    except Exception as e:
        print(f"Error: {e}", file=__import__("sys").stderr)
        __import__("sys").exit(1)


def cmd_mailbox_list(args: argparse.Namespace, conn) -> None:
    if args.domain:
        rows = conn.execute(
            """SELECT m.id, m.email, m.quota_mb, m.used_mb, m.enabled, m.created_at
               FROM mailboxes m
               JOIN users u ON m.user_id = u.id
               JOIN domains d ON u.domain_id = d.id
               WHERE d.domain = ? ORDER BY m.email""",
            (args.domain.lower().strip(),),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, email, quota_mb, used_mb, enabled, created_at FROM mailboxes ORDER BY email"
        ).fetchall()
    if not rows:
        print("No mailboxes found.")
        return
    print(f"{'ID':<4} {'Email':<40} {'Quota':<8} {'Used':<8} {'Active':<7} {'Created':<20}")
    print("-" * 87)
    for r in rows:
        active = "yes" if r["enabled"] else "no"
        print(f"{r['id']:<4} {r['email']:<40} {r['quota_mb']:<8} {r['used_mb']:<8} {active:<7} {r['created_at']:<20}")


def cmd_mailbox_delete(args: argparse.Namespace, conn) -> None:
    email = args.email.lower().strip()
    cur = conn.execute("DELETE FROM mailboxes WHERE email = ?", (email,))
    conn.commit()
    if cur.rowcount:
        print(f"Mailbox '{email}' deleted.")
    else:
        print(f"Mailbox '{email}' not found.", file=__import__("sys").stderr)
        __import__("sys").exit(1)
