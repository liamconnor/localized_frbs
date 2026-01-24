"""
Use Claude API to parse FRB announcements and extract structured data.
"""

import anthropic
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class FRBData:
    """Structured FRB data extracted from an announcement."""
    name: str                    # Internal name (e.g., 'fen')
    TNSname: str                 # TNS name (e.g., 'FRB 20220204A')
    ra: float                    # Right ascension in degrees
    dec: float                   # Declination in degrees
    dm_exgal: float              # Extragalactic DM in pc/cm^3
    redshift: float              # Redshift
    redshift_type: str           # 'spec' or 'phot'
    survey: str                  # Detecting telescope/survey
    secure_host: str             # 'yes' or 'no'
    source_url: str              # URL of the announcement
    # Optional fields
    dm_opt: Optional[float] = None
    rm: Optional[float] = None
    rm_err: Optional[float] = None
    mjd: Optional[float] = None


EXTRACTION_PROMPT = """You are an expert astronomer helping to build a database of Fast Radio Bursts (FRBs) with measured redshifts.

Given the following announcement (ATel or arXiv abstract), extract any NEW FRB localizations with redshifts.

IMPORTANT CRITERIA:
- Must have a spectroscopic or photometric redshift measurement
- Must have coordinates (RA, Dec) - ideally sub-arcsecond localization
- Must have a DM (dispersion measure) measurement
- Skip FRBs that are just mentioned but not newly localized in this announcement
- Skip FRBs from CHIME/FRB catalogs that don't have redshifts

For each NEW FRB with a redshift in this announcement, extract:
- TNS name (e.g., "FRB 20220204A")
- RA in degrees (convert from HMS if needed)
- Dec in degrees (convert from DMS if needed)
- DM (dispersion measure) in pc/cm^3 - use extragalactic DM if available, otherwise total DM
- Redshift value
- Redshift type: "spec" for spectroscopic, "phot" for photometric
- Survey/telescope that detected it (e.g., DSA-110, ASKAP, CHIME, MeerKAT, FAST, Parkes, VLA)
- Whether host association is secure: "yes" or "no"
- RM (rotation measure) if available, otherwise null
- RM error if available, otherwise null

Respond with a JSON array of objects. If no new FRBs with redshifts are announced, return an empty array [].

Example response:
```json
[
  {{
    "TNSname": "FRB 20240101A",
    "ra": 180.5,
    "dec": -45.2,
    "dm_exgal": 350.5,
    "redshift": 0.25,
    "redshift_type": "spec",
    "survey": "ASKAP",
    "secure_host": "yes",
    "rm": 125.5,
    "rm_err": 2.3
  }}
]
```

ANNOUNCEMENT:
Title: {title}
Authors: {authors}
Date: {date}
Source: {source} ({source_id})

Content:
{abstract}

Extract any new FRBs with redshifts from this announcement. Return ONLY the JSON array, no other text."""


def parse_announcement(
    title: str,
    authors: str,
    date: str,
    source: str,
    source_id: str,
    abstract: str,
    source_url: str,
    api_key: Optional[str] = None
) -> list[FRBData]:
    """
    Use Claude to parse an announcement and extract FRB data.

    Returns a list of FRBData objects (may be empty if no new FRBs found).
    """
    api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = EXTRACTION_PROMPT.format(
        title=title,
        authors=authors,
        date=date,
        source=source,
        source_id=source_id,
        abstract=abstract
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text.strip()

    # Extract JSON from response (handle markdown code blocks)
    if '```json' in response_text:
        response_text = response_text.split('```json')[1].split('```')[0]
    elif '```' in response_text:
        response_text = response_text.split('```')[1].split('```')[0]

    try:
        frbs_raw = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        print(f"Response was: {response_text}")
        return []

    # Convert to FRBData objects
    frbs = []
    for frb in frbs_raw:
        try:
            frb_data = FRBData(
                name=frb.get('TNSname', '').replace('FRB ', '').replace(' ', ''),
                TNSname=frb.get('TNSname', ''),
                ra=float(frb.get('ra', 0)),
                dec=float(frb.get('dec', 0)),
                dm_exgal=float(frb.get('dm_exgal', 0)),
                dm_opt=float(frb.get('dm_exgal', 0)),  # Use same as dm_exgal
                redshift=float(frb.get('redshift', 0)),
                redshift_type=frb.get('redshift_type', 'spec'),
                survey=frb.get('survey', 'unknown'),
                secure_host=frb.get('secure_host', 'no'),
                source_url=source_url,
                rm=frb.get('rm'),
                rm_err=frb.get('rm_err'),
                mjd=frb.get('mjd')
            )
            frbs.append(frb_data)
        except (ValueError, KeyError) as e:
            print(f"Error parsing FRB data: {e}")
            continue

    return frbs


def process_announcements(announcements: list, api_key: Optional[str] = None) -> list[FRBData]:
    """
    Process a list of announcements and extract all FRB data.

    Args:
        announcements: List of Announcement objects from fetch_sources.py
        api_key: Anthropic API key (or use ANTHROPIC_API_KEY env var)

    Returns:
        List of FRBData objects
    """
    all_frbs = []

    for ann in announcements:
        print(f"\nProcessing: [{ann.source}] {ann.title[:60]}...")

        frbs = parse_announcement(
            title=ann.title,
            authors=ann.authors,
            date=ann.date,
            source=ann.source,
            source_id=ann.id,
            abstract=ann.abstract,
            source_url=ann.url,
            api_key=api_key
        )

        if frbs:
            print(f"  Found {len(frbs)} FRB(s): {[f.TNSname for f in frbs]}")
            all_frbs.extend(frbs)
        else:
            print(f"  No new FRBs with redshifts found")

    return all_frbs


if __name__ == '__main__':
    # Test with a sample announcement
    test_abstract = """
    We report the localization and host galaxy identification of FRB 20240501A,
    detected by the Deep Synoptic Array (DSA-110). The burst was detected with
    a DM of 425.3 pc/cm^3 and localized to RA=12:34:56.7, Dec=+45:12:34.5 (J2000)
    with an uncertainty of 0.5 arcsec. Follow-up spectroscopy with Keck/LRIS
    reveals the host galaxy at a redshift of z=0.312. The host is a star-forming
    galaxy with stellar mass log(M*/Msun) = 10.2.
    """

    frbs = parse_announcement(
        title="Localization and host of FRB 20240501A",
        authors="Smith et al.",
        date="2024-05-15",
        source="atel",
        source_id="ATel#12345",
        abstract=test_abstract,
        source_url="https://www.astronomerstelegram.org/?read=12345"
    )

    for frb in frbs:
        print(json.dumps(asdict(frb), indent=2))
