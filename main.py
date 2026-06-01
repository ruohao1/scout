from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scout")
    subparsers = parser.add_subparsers(dest="command")

    db_parser = subparsers.add_parser("db", help="Manage database schema")
    db_subparsers = db_parser.add_subparsers(dest="db_command")

    setup_parser = db_subparsers.add_parser("setup", help="Create required database schema")
    setup_parser.set_defaults(handler=setup_database_command)

    jobs_parser = subparsers.add_parser("jobs", help="Manage job imports")
    jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command")

    import_mock_parser = jobs_subparsers.add_parser("import-mock", help="Import mock provider job responses")
    import_mock_parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of mock jobs to import",
    )
    import_mock_parser.add_argument(
        "--fixture",
        type=Path,
        help="JSON fixture file containing a list of raw mock provider jobs or an object with a jobs list",
    )
    import_mock_parser.add_argument(
        "--index",
        action="store_true",
        help="Index imported jobs for search after insertion",
    )
    import_mock_parser.add_argument(
        "--source",
        default="mock_jobs",
        help="Source name stored on imported jobs",
    )
    import_mock_parser.set_defaults(handler=import_mock_jobs)

    auth_parser = subparsers.add_parser("auth", help="Manage provider authentication")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_provider")

    openai_parser = auth_subparsers.add_parser("openai", help="Manage OpenAI authentication")
    openai_subparsers = openai_parser.add_subparsers(dest="openai_command")

    login_parser = openai_subparsers.add_parser("login", help="Log in with OpenAI OAuth")
    login_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Print the authorization URL instead of opening a browser",
    )
    login_parser.set_defaults(handler=login_openai)

    return parser


def login_openai(args: argparse.Namespace) -> int:
    from providers.openai_auth import OAuthError, OpenAIAuthProvider

    try:
        OpenAIAuthProvider().login_browser(open_browser=not args.no_browser)
    except OAuthError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def setup_database_command(args: argparse.Namespace) -> int:
    from db import setup_database

    setup_database()
    print("Database schema is ready.")
    return 0


def import_mock_jobs(args: argparse.Namespace) -> int:
    from services import MockJobProviderAdapter, MockJobProviderClient, import_jobs

    if args.count < 0:
        print("error: --count must be greater than or equal to 0", file=sys.stderr)
        return 1

    try:
        result = import_jobs(
            client=MockJobProviderClient(fixture_path=args.fixture),
            adapter=MockJobProviderAdapter(source=args.source),
            count=args.count,
            should_index=args.index,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Imported {len(result.created)} mock jobs.")
    if result.skipped:
        print(f"Skipped {result.skipped} duplicate mock jobs.")
    if args.index:
        print(f"Indexed {result.indexed} mock jobs.")
    for job in result.created:
        print(job["id"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
