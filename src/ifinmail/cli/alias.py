import argparse


def register_alias_subcommands(sub) -> None:
    p = sub.add_parser("alias", help="Manage email aliases")
    p_sub = p.add_subparsers(dest="action")
    p_sub.required = True

    p_add = p_sub.add_parser("add", help="Create an alias")
    p_add.add_argument("source", help="Source address (e.g. info@example.com)")
    p_add.add_argument("target", help="Target address (e.g. user@example.com)")
    p_add.set_defaults(fn=cmd_alias_add)

    p_list = p_sub.add_parser("list", help="List aliases")
    p_list.add_argument("--domain", "-d", default=None, help="Filter by domain")
    p_list.set_defaults(fn=cmd_alias_list)

    p_rm = p_sub.add_parser("remove", help="Remove an alias")
    p_rm.add_argument("source", help="Source address to remove")
    p_rm.set_defaults(fn=cmd_alias_remove)


def _ensure_domain(conn, email: str) -> int | None:
    domain_part = email.split("@", 1)[-1]
    row = conn.execute("SELECT id FROM domains WHERE domain = ?", (domain_part,)).fetchone()
    if not row:
        print(f"Domain '{domain_part}' not found.", file=__import__("sys").stderr)
        return None
    return row["id"]


def cmd_alias_add(args: argparse.Namespace, conn) -> None:
    source = args.source.lower().strip()
    target = args.target.lower().strip()
    domain_id = _ensure_domain(conn, source)
    if domain_id is None:
        __import__("sys").exit(1)
    try:
        conn.execute(
            "INSERT INTO aliases (source, target, domain_id) VALUES (?, ?, ?)",
            (source, target, domain_id),
        )
        conn.commit()
        print(f"Alias '{source} → {target}' created.")
    except Exception as e:
        print(f"Error: {e}", file=__import__("sys").stderr)
        __import__("sys").exit(1)


def cmd_alias_list(args: argparse.Namespace, conn) -> None:
    if args.domain:
        rows = conn.execute(
            """SELECT a.id, a.source, a.target, a.enabled, a.created_at
               FROM aliases a JOIN domains d ON a.domain_id = d.id
               WHERE d.domain = ? ORDER BY a.source""",
            (args.domain.lower().strip(),),
        ).fetchall()
    else:
        rows = conn.execute("SELECT id, source, target, enabled, created_at FROM aliases ORDER BY source").fetchall()
    if not rows:
        print("No aliases found.")
        return
    print(f"{'ID':<4} {'Source':<40} {'Target':<40} {'Active':<7} {'Created':<20}")
    print("-" * 91)
    for r in rows:
        active = "yes" if r["enabled"] else "no"
        print(f"{r['id']:<4} {r['source']:<40} {r['target']:<40} {active:<7} {r['created_at']:<20}")


def cmd_alias_remove(args: argparse.Namespace, conn) -> None:
    source = args.source.lower().strip()
    cur = conn.execute("DELETE FROM aliases WHERE source = ?", (source,))
    conn.commit()
    if cur.rowcount:
        print(f"Alias '{source}' removed.")
    else:
        print(f"Alias '{source}' not found.", file=__import__("sys").stderr)
        __import__("sys").exit(1)
