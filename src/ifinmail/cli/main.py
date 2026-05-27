import argparse
import sys

from ifinmail.cli.alias import register_alias_subcommands
from ifinmail.cli.domain import register_domain_subcommands
from ifinmail.cli.mailbox import register_mailbox_subcommands
from ifinmail.cli.user import register_user_subcommands
from ifinmail.db.database import init_db


def cli(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="ifinmail",
        description="ifinmail App — Admin CLI",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to the SQLite database (default: ~/.ifinmail/admin.db)",
    )

    sub = parser.add_subparsers(dest="command")
    sub.required = True

    cmd_status = sub.add_parser("status", help="Show system status")
    cmd_status.set_defaults(fn=cmd_status_fn)

    register_domain_subcommands(sub)
    register_user_subcommands(sub)
    register_mailbox_subcommands(sub)
    register_alias_subcommands(sub)

    cmd_smtp = sub.add_parser("smtp", help="Start the SMTP receiver server")
    cmd_smtp.set_defaults(fn=cmd_smtp_fn)

    cmd_serve = sub.add_parser("serve", help="Start the API web server")
    cmd_serve.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    cmd_serve.add_argument("--port", type=int, default=8025, help="Bind port (default: 8025)")
    cmd_serve.set_defaults(fn=cmd_serve_fn)

    args = parser.parse_args(argv)
    args_fn = getattr(args, "fn", None)
    if args_fn is cmd_smtp_fn or args_fn is cmd_serve_fn:
        args_fn(args)
    elif args_fn:
        db_path = args.db
        conn = init_db(db_path)
        try:
            args_fn(args, conn)
        finally:
            conn.close()
    else:
        parser.print_help()
        sys.exit(1)


def cmd_smtp_fn(_args: argparse.Namespace) -> None:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    from ifinmail.smtp.server import start_smtp_server

    start_smtp_server()


def cmd_serve_fn(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("ifinmail.api.app:app", host=args.host, port=args.port, reload=False)


def cmd_status_fn(args: argparse.Namespace, conn) -> None:
    cur = conn.execute("SELECT COUNT(*) AS cnt FROM domains")
    domains = cur.fetchone()["cnt"]
    cur = conn.execute("SELECT COUNT(*) AS cnt FROM users")
    users = cur.fetchone()["cnt"]
    cur = conn.execute("SELECT COUNT(*) AS cnt FROM mailboxes")
    mailboxes = cur.fetchone()["cnt"]
    cur = conn.execute("SELECT COUNT(*) AS cnt FROM aliases")
    aliases = cur.fetchone()["cnt"]

    print(f"Domains:   {domains}")
    print(f"Users:     {users}")
    print(f"Mailboxes: {mailboxes}")
    print(f"Aliases:   {aliases}")
