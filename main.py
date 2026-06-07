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

    import_adzuna_parser = jobs_subparsers.add_parser("import-adzuna", help="Import jobs from the Adzuna API")
    import_adzuna_parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of Adzuna jobs to import",
    )
    import_adzuna_parser.add_argument(
        "--country",
        default="gb",
        help="Adzuna country code, for example gb, us, fr, or de",
    )
    import_adzuna_parser.add_argument(
        "--what",
        help="Search query passed to Adzuna, for example 'python developer'",
    )
    import_adzuna_parser.add_argument(
        "--where",
        help="Location query passed to Adzuna, for example 'London'",
    )
    import_adzuna_parser.add_argument(
        "--app-id",
        help="Adzuna app id; defaults to ADZUNA_APP_ID",
    )
    import_adzuna_parser.add_argument(
        "--app-key",
        help="Adzuna app key; defaults to ADZUNA_APP_KEY",
    )
    import_adzuna_parser.add_argument(
        "--results-per-page",
        type=int,
        default=50,
        help="Adzuna page size used while fetching results",
    )
    index_group = import_adzuna_parser.add_mutually_exclusive_group()
    index_group.add_argument(
        "--index",
        dest="index",
        action="store_true",
        help="Index imported jobs for search after insertion (default)",
    )
    index_group.add_argument(
        "--no-index",
        dest="index",
        action="store_false",
        help="Import jobs without indexing them for search",
    )
    import_adzuna_parser.add_argument(
        "--source",
        default="adzuna",
        help="Source name stored on imported jobs",
    )
    import_adzuna_parser.set_defaults(handler=import_adzuna_jobs)
    import_adzuna_parser.set_defaults(index=True)

    candidate_parser = subparsers.add_parser("candidate", help="Manage candidate knowledge")
    candidate_subparsers = candidate_parser.add_subparsers(dest="candidate_command")

    migrate_profile_parser = candidate_subparsers.add_parser("migrate-profile", help="Migrate a legacy profile to candidate knowledge")
    migrate_profile_parser.add_argument(
        "--profile-id",
        help="Legacy profile id to migrate; defaults to the newest profile",
    )
    migrate_profile_parser.set_defaults(handler=migrate_profile)

    seed_fake_parser = candidate_subparsers.add_parser("seed-fake", help="Seed a reusable fake candidate for local testing")
    seed_fake_parser.add_argument(
        "--fixture",
        type=Path,
        help="Candidate JSON fixture to seed; defaults to the bundled Maya Chen fixture",
    )
    seed_fake_parser.add_argument(
        "--no-index",
        dest="index",
        action="store_false",
        help="Seed candidate evidence without indexing embeddings",
    )
    seed_fake_parser.add_argument(
        "--no-target-profile",
        dest="target_profile",
        action="store_false",
        help="Seed only candidate knowledge without creating a target profile",
    )
    seed_fake_parser.set_defaults(handler=seed_fake_candidate_command)
    seed_fake_parser.set_defaults(index=True, target_profile=True)

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


def import_adzuna_jobs(args: argparse.Namespace) -> int:
    from services import AdzunaJobProviderAdapter, AdzunaJobProviderClient, import_jobs

    if args.count < 0:
        print("error: --count must be greater than or equal to 0", file=sys.stderr)
        return 1

    try:
        result = import_jobs(
            client=AdzunaJobProviderClient(
                app_id=args.app_id,
                app_key=args.app_key,
                country=args.country,
                what=args.what,
                where=args.where,
                results_per_page=args.results_per_page,
            ),
            adapter=AdzunaJobProviderAdapter(source=args.source),
            count=args.count,
            should_index=args.index,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Imported {len(result.created)} Adzuna jobs.")
    if result.skipped:
        print(f"Skipped {result.skipped} duplicate Adzuna jobs.")
    if args.index:
        print(f"Indexed {result.indexed} Adzuna jobs.")
    for job in result.created:
        print(job["id"])
    return 0


def migrate_profile(args: argparse.Namespace) -> int:
    from services import LegacyProfileNotFoundError, migrate_profiles_to_candidate

    try:
        result = migrate_profiles_to_candidate(source_profile_id=args.profile_id)
    except LegacyProfileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Candidate: {result['candidate_id']}")
    if result["document_id"]:
        print(f"Document: {result['document_id']}")
    print(f"Evidence migrated: {result['evidence_count']}")
    if result["target_profile_id"]:
        print(f"Target profile: {result['target_profile_id']}")
    print(f"Evidence indexed: {result['indexed_count']}")
    return 0


def seed_fake_candidate_command(args: argparse.Namespace) -> int:
    from services import CandidateSeedFixtureError, seed_fake_candidate

    try:
        result = seed_fake_candidate(fixture_path=args.fixture, should_index=args.index, with_target_profile=args.target_profile)
    except CandidateSeedFixtureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Candidate: {result['candidate_id']}")
    print(f"Document: {result['document_id']}")
    print(f"Evidence seeded: {result['evidence_count']}")
    if result["target_profile_id"]:
        print(f"Target profile: {result['target_profile_id']}")
    if args.index:
        print(f"Evidence indexed: {result['indexed_count']}")
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
