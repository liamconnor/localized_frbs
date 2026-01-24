"""
Fetch potential FRB announcements from ATels and arXiv.
"""

import feedparser
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import re


@dataclass
class Announcement:
    """A potential FRB announcement."""
    source: str  # 'atel' or 'arxiv'
    id: str      # ATel number or arXiv ID
    title: str
    authors: str
    date: str
    abstract: str
    url: str


def fetch_atels(days_back: int = 7) -> list[Announcement]:
    """
    Fetch recent ATels mentioning FRB.

    ATel RSS feed: https://www.astronomerstelegram.org/?rss
    """
    announcements = []

    # ATel RSS feed
    feed_url = "https://www.astronomerstelegram.org/?rss"

    try:
        feed = feedparser.parse(feed_url)

        cutoff_date = datetime.now() - timedelta(days=days_back)

        for entry in feed.entries:
            title = entry.get('title', '')
            summary = entry.get('summary', '')

            # Filter for FRB-related ATels
            if 'FRB' in title.upper() or 'FRB' in summary.upper() or \
               'FAST RADIO BURST' in title.upper() or 'FAST RADIO BURST' in summary.upper():

                # Extract ATel number from link
                link = entry.get('link', '')
                atel_match = re.search(r'\?read=(\d+)', link)
                atel_id = atel_match.group(1) if atel_match else 'unknown'

                # Parse date
                published = entry.get('published', '')

                announcements.append(Announcement(
                    source='atel',
                    id=f"ATel#{atel_id}",
                    title=title,
                    authors=entry.get('author', ''),
                    date=published,
                    abstract=summary,
                    url=link
                ))

    except Exception as e:
        print(f"Error fetching ATels: {e}")

    return announcements


def fetch_arxiv(days_back: int = 7, max_results: int = 50) -> list[Announcement]:
    """
    Fetch recent arXiv papers about FRBs.

    Uses arXiv API: https://arxiv.org/help/api
    """
    announcements = []

    # arXiv API query for FRB papers in astro-ph
    base_url = "http://export.arxiv.org/api/query"

    # Search for FRB in title or abstract, in astro-ph
    query = 'all:"fast radio burst" OR all:FRB AND cat:astro-ph*'

    params = {
        'search_query': query,
        'start': 0,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }

    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()

        # Parse XML response
        root = ET.fromstring(response.content)

        # Namespace for Atom feed
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }

        cutoff_date = datetime.now() - timedelta(days=days_back)

        for entry in root.findall('atom:entry', ns):
            # Get published date
            published_str = entry.find('atom:published', ns).text
            published_date = datetime.fromisoformat(published_str.replace('Z', '+00:00'))

            # Skip if too old
            if published_date.replace(tzinfo=None) < cutoff_date:
                continue

            # Extract fields
            title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
            abstract = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')

            # Get arXiv ID
            arxiv_id = entry.find('atom:id', ns).text.split('/')[-1]

            # Get authors
            authors = [a.find('atom:name', ns).text
                      for a in entry.findall('atom:author', ns)]
            authors_str = ', '.join(authors[:5])
            if len(authors) > 5:
                authors_str += f' et al. ({len(authors)} authors)'

            # Get PDF link
            pdf_link = None
            for link in entry.findall('atom:link', ns):
                if link.get('title') == 'pdf':
                    pdf_link = link.get('href')
                    break

            announcements.append(Announcement(
                source='arxiv',
                id=arxiv_id,
                title=title,
                authors=authors_str,
                date=published_str[:10],
                abstract=abstract[:2000],  # Truncate long abstracts
                url=pdf_link or f"https://arxiv.org/abs/{arxiv_id}"
            ))

    except Exception as e:
        print(f"Error fetching arXiv: {e}")

    return announcements


def filter_localization_announcements(announcements: list[Announcement]) -> list[Announcement]:
    """
    Filter for announcements that likely contain new FRB localizations/redshifts.

    Keywords: redshift, host galaxy, localization, spectroscopic, z =
    """
    keywords = [
        'redshift', 'host galaxy', 'host association', 'localization',
        'spectroscopic', 'z =', 'z=', 'photometric redshift',
        'optical counterpart', 'localized', 'arcsec'
    ]

    filtered = []
    for ann in announcements:
        text = (ann.title + ' ' + ann.abstract).lower()
        if any(kw.lower() in text for kw in keywords):
            filtered.append(ann)

    return filtered


def fetch_all_sources(days_back: int = 7) -> list[Announcement]:
    """Fetch from all sources and filter for likely localizations."""

    print(f"Fetching announcements from the last {days_back} days...")

    atels = fetch_atels(days_back)
    print(f"  Found {len(atels)} FRB-related ATels")

    arxiv = fetch_arxiv(days_back)
    print(f"  Found {len(arxiv)} FRB-related arXiv papers")

    all_announcements = atels + arxiv

    # Filter for localization-related announcements
    filtered = filter_localization_announcements(all_announcements)
    print(f"  {len(filtered)} appear to be about localizations/redshifts")

    return filtered


if __name__ == '__main__':
    announcements = fetch_all_sources(days_back=30)

    for ann in announcements:
        print(f"\n{'='*60}")
        print(f"[{ann.source}] {ann.id}")
        print(f"Title: {ann.title}")
        print(f"Date: {ann.date}")
        print(f"URL: {ann.url}")
        print(f"Abstract: {ann.abstract[:300]}...")
