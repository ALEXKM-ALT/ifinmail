import argparse


def register_domain_subcommands(sub) -> None:
    p = sub.add_parser("domain", help="Manage domains")
    p_sub = p.add_subparsers(dest="action")
    p_sub.required = True

    p_add = p_sub.add_parser("add", help="Register a new domain")
    p_add.add_argument("domain", help="Domain name (e.g. example.com)")
    p_add.set_defaults(fn=cmd_domain_add)

    p_list = p_sub.add_parser("list", help="List all domains")
    p_list.set_defaults(fn=cmd_domain_list)

    p_rm = p_sub.add_parser("remove", help="Remove a domain")
    p_rm.add_argument("domain", help="Domain name to remove")
    p_rm.set_defaults(fn=cmd_domain_remove)

    p_verify = p_sub.add_parser("verify", help="Show DNS verification info")
    p_verify.add_argument("domain", help="Domain name")
    p_verify.set_defaults(fn=cmd_domain_verify)


def cmd_domain_add(args: argparse.Namespace, conn) -> None:
    domain = args.domain.lower().strip()
    try:
        conn.execute(
            "INSERT INTO domains (domain) VALUES (?)",
            (domain,),
        )
        conn.commit()
        print(f"Domain '{domain}' registered.")
    except Exception as e:
        print(f"Error: {e}", file=__import__("sys").stderr)
        __import__("sys").exit(1)


def cmd_domain_list(args: argparse.Namespace, conn) -> None:
    rows = conn.execute("SELECT id, domain, verified, created_at FROM domains ORDER BY domain").fetchall()
    if not rows:
        print("No domains registered.")
        return
    print(f"{'ID':<4} {'Domain':<30} {'Verified':<9} {'Created':<20}")
    print("-" * 63)
    for r in rows:
        verified = "yes" if r["verified"] else "no"
        print(f"{r['id']:<4} {r['domain']:<30} {verified:<9} {r['created_at']:<20}")


def cmd_domain_remove(args: argparse.Namespace, conn) -> None:
    domain = args.domain.lower().strip()
    cur = conn.execute("DELETE FROM domains WHERE domain = ?", (domain,))
    conn.commit()
    if cur.rowcount:
        print(f"Domain '{domain}' removed.")
    else:
        print(f"Domain '{domain}' not found.", file=__import__("sys").stderr)
        __import__("sys").exit(1)


def cmd_domain_verify(args: argparse.Namespace, conn) -> None:
    domain = args.domain.lower().strip()
    row = conn.execute(
        "SELECT id, domain, verified FROM domains WHERE domain = ?",
        (domain,),
    ).fetchone()
    if not row:
        print(f"Domain '{domain}' not found.", file=__import__("sys").stderr)
        __import__("sys").exit(1)

    print(f"Domain:        {domain}")
    print(f"Status:        {'Verified' if row['verified'] else 'Pending verification'}")
    print()
    print("Required DNS records:")
    print(f"  MX        mail.{domain}    →    <server IP>")
    print(f"  TXT       {domain}         →    v=spf1 mx -all")
    print(f"  TXT       default._domainkey.{domain}")
    print(f"  TXT       _dmarc.{domain}  →    v=DMARC1; p=quarantine")
    print()
    print("Run verification once DNS is configured:")
    print(f"  ifinmail domain verify-set {domain}")
