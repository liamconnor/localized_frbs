#!/usr/bin/env python3
"""
Main script to check for new FRB localizations and update the database.

This script:
1. Fetches recent ATels and arXiv papers about FRBs
2. Uses Claude to extract structured data from announcements
3. Checks for duplicates against the existing database
4. Creates a report of new FRBs found (for PR review)

Usage:
    python main.py --db frbs.db --days 7 --dry-run
    python main.py --db frbs.db --days 7 --update
"""

import argparse
import json
import os
import sys
from datetime import datetime
from dataclasses import asdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_sources import fetch_all_sources
from parse_with_claude import process_announcements
from update_database import add_frb_to_database, get_database_stats


def generate_report(new_frbs: list, db_path: str) -> str:
    """Generate a markdown report of new FRBs found."""

    report = f"""# FRB Database Update Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
**Database:** {db_path}

## Summary

Found **{len(new_frbs)}** new FRB(s) with redshifts.

"""

    if not new_frbs:
        report += "_No new FRBs found._\n"
        return report

    report += "## New FRBs\n\n"

    for frb in new_frbs:
        frb_dict = asdict(frb) if hasattr(frb, '__dataclass_fields__') else frb

        report += f"""### {frb_dict.get('TNSname', 'Unknown')}

| Field | Value |
|-------|-------|
| RA | {frb_dict.get('ra', 'N/A'):.6f} deg |
| Dec | {frb_dict.get('dec', 'N/A'):.6f} deg |
| DM | {frb_dict.get('dm_exgal', 'N/A')} pc/cm³ |
| Redshift | {frb_dict.get('redshift', 'N/A')} ({frb_dict.get('redshift_type', 'N/A')}) |
| Survey | {frb_dict.get('survey', 'N/A')} |
| Source | [{frb_dict.get('source_url', 'N/A')}]({frb_dict.get('source_url', '#')}) |

"""

    return report


def main():
    parser = argparse.ArgumentParser(description='Check for new FRB localizations')
    parser.add_argument('--db', required=True, help='Path to SQLite database')
    parser.add_argument('--days', type=int, default=7, help='Days to look back')
    parser.add_argument('--dry-run', action='store_true', help='Do not modify database')
    parser.add_argument('--update', action='store_true', help='Update database with new FRBs')
    parser.add_argument('--report', type=str, help='Path to save markdown report')
    parser.add_argument('--json', type=str, help='Path to save JSON output')

    args = parser.parse_args()

    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Show current database stats
    print("\n" + "=" * 60)
    print("Current Database Statistics")
    print("=" * 60)
    stats = get_database_stats(args.db)
    print(f"Total FRBs: {stats['total']}")
    print(f"With redshift: {stats['with_redshift']}")
    print(f"Redshift range: {stats['z_min']:.4f} - {stats['z_max']:.4f}")

    # Fetch announcements
    print("\n" + "=" * 60)
    print(f"Fetching announcements from the last {args.days} days")
    print("=" * 60)

    announcements = fetch_all_sources(days_back=args.days)

    if not announcements:
        print("No relevant announcements found.")
        return

    # Parse announcements with Claude
    print("\n" + "=" * 60)
    print("Parsing announcements with Claude")
    print("=" * 60)

    frbs = process_announcements(announcements)

    if not frbs:
        print("\nNo new FRBs with redshifts found in announcements.")
        return

    print(f"\nFound {len(frbs)} potential new FRB(s)")

    # Check against database and optionally update
    print("\n" + "=" * 60)
    print("Checking against existing database")
    print("=" * 60)

    new_frbs = []
    for frb in frbs:
        frb_dict = asdict(frb)
        success, message = add_frb_to_database(
            args.db,
            frb_dict,
            dry_run=not args.update
        )
        print(f"  {frb.TNSname}: {message}")

        if success:
            new_frbs.append(frb)

    # Generate report
    report = generate_report(new_frbs, args.db)

    if args.report:
        with open(args.report, 'w') as f:
            f.write(report)
        print(f"\nReport saved to: {args.report}")
    else:
        print("\n" + report)

    # Save JSON output
    if args.json:
        output = {
            'timestamp': datetime.now().isoformat(),
            'days_checked': args.days,
            'announcements_found': len(announcements),
            'new_frbs': [asdict(f) for f in new_frbs]
        }
        with open(args.json, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"JSON output saved to: {args.json}")

    # Set GitHub Actions output
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"new_frbs_count={len(new_frbs)}\n")
            f.write(f"new_frbs_names={','.join(f.TNSname for f in new_frbs)}\n")

    print("\n" + "=" * 60)
    print(f"Done! Found {len(new_frbs)} new FRB(s)")
    print("=" * 60)


if __name__ == '__main__':
    main()
