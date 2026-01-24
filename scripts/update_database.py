"""
Update the FRB SQLite database with new entries.
Handles deduplication by TNS name and coordinates.
"""

import sqlite3
import csv
import os
from dataclasses import asdict
from typing import Optional
from math import sqrt


def angular_separation(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """
    Calculate angular separation in arcseconds between two positions.
    Simple approximation valid for small separations.
    """
    # Convert to radians for cos calculation
    import math
    dec_avg = math.radians((dec1 + dec2) / 2)

    d_ra = (ra1 - ra2) * math.cos(dec_avg) * 3600  # arcsec
    d_dec = (dec1 - dec2) * 3600  # arcsec

    return sqrt(d_ra**2 + d_dec**2)


def check_duplicate(
    cursor: sqlite3.Cursor,
    tns_name: str,
    ra: float,
    dec: float,
    match_radius_arcsec: float = 10.0
) -> Optional[str]:
    """
    Check if an FRB is already in the database.

    Returns the name of the matching FRB if found, None otherwise.
    """
    # First check by TNS name (exact match)
    # Handle both "FRB20220610A" and "FRB 20220610A" formats
    clean_name = tns_name.replace('FRB ', 'FRB').replace(' ', '')
    cursor.execute(
        "SELECT Name FROM frbs WHERE Name = ? OR Name = ?",
        (tns_name, clean_name)
    )
    result = cursor.fetchone()
    if result:
        return result[0]  # Return the name

    # Also check by coordinates (within match_radius)
    cursor.execute("SELECT Name, ra, dec FROM frbs")
    for row in cursor.fetchall():
        existing_name, existing_ra, existing_dec = row
        if existing_ra and existing_dec:
            sep = angular_separation(ra, dec, existing_ra, existing_dec)
            if sep < match_radius_arcsec:
                return existing_name

    return None


def add_frb_to_database(
    db_path: str,
    frb_data: dict,
    dry_run: bool = False
) -> tuple[bool, str]:
    """
    Add a new FRB to the database.

    Args:
        db_path: Path to SQLite database
        frb_data: Dictionary with FRB fields
        dry_run: If True, don't actually modify the database

    Returns:
        Tuple of (success: bool, message: str)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check for duplicates
        existing = check_duplicate(
            cursor,
            frb_data.get('TNSname', ''),
            frb_data.get('ra', 0),
            frb_data.get('dec', 0)
        )

        if existing:
            return False, f"Duplicate: matches existing FRB '{existing}'"

        if dry_run:
            return True, f"Would add: {frb_data.get('TNSname')}"

        # Prepare the data for insertion
        # Match the actual database schema
        tns_name = frb_data.get('TNSname', frb_data.get('name', ''))
        clean_name = tns_name.replace('FRB ', 'FRB').replace(' ', '')

        row = {
            'Name': clean_name,
            'ra': frb_data.get('ra', 0),
            'dec': frb_data.get('dec', 0),
            'DM': frb_data.get('dm', frb_data.get('dm_exgal', frb_data.get('DM'))),
            'z': frb_data.get('z', frb_data.get('redshift')),
            'RM': frb_data.get('rm', frb_data.get('RM')),
            'RM_err': frb_data.get('rm_err', frb_data.get('RM_err')),
            'telescope': frb_data.get('telescope', frb_data.get('survey', 'unknown')),
            'repeater': frb_data.get('repeater', 'no'),
            'refs': frb_data.get('refs', frb_data.get('reference', '')),
        }

        # Get column names from existing table
        cursor.execute("PRAGMA table_info(frbs)")
        columns = [col[1] for col in cursor.fetchall()]

        # Filter row to only include existing columns
        row = {k: v for k, v in row.items() if k in columns}

        # Insert
        placeholders = ', '.join(['?' for _ in row])
        column_names = ', '.join(row.keys())

        cursor.execute(
            f"INSERT INTO frbs ({column_names}) VALUES ({placeholders})",
            list(row.values())
        )

        conn.commit()
        return True, f"Added: {frb_data.get('TNSname')}"

    except Exception as e:
        return False, f"Error: {str(e)}"

    finally:
        conn.close()


def export_to_csv(db_path: str, csv_path: str):
    """Export the database to CSV format."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM frbs")
    rows = cursor.fetchall()

    cursor.execute("PRAGMA table_info(frbs)")
    columns = [col[1] for col in cursor.fetchall()]

    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    conn.close()
    print(f"Exported {len(rows)} FRBs to {csv_path}")


def get_database_stats(db_path: str) -> dict:
    """Get statistics about the current database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM frbs")
    stats['total'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM frbs WHERE z IS NOT NULL AND z != ''")
    stats['with_redshift'] = cursor.fetchone()[0]

    cursor.execute("SELECT telescope, COUNT(*) FROM frbs GROUP BY telescope ORDER BY COUNT(*) DESC")
    stats['by_survey'] = dict(cursor.fetchall())

    cursor.execute("SELECT MIN(z), MAX(z) FROM frbs WHERE z IS NOT NULL AND z != ''")
    z_range = cursor.fetchone()
    stats['z_min'] = z_range[0]
    stats['z_max'] = z_range[1]

    conn.close()
    return stats


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python update_database.py <db_path> [--stats]")
        sys.exit(1)

    db_path = sys.argv[1]

    if '--stats' in sys.argv:
        stats = get_database_stats(db_path)
        print(f"\nDatabase: {db_path}")
        print(f"Total FRBs: {stats['total']}")
        print(f"With redshift: {stats['with_redshift']}")
        print(f"Redshift range: {stats['z_min']:.4f} - {stats['z_max']:.4f}")
        print(f"\nBy survey:")
        for survey, count in stats['by_survey'].items():
            print(f"  {survey}: {count}")
