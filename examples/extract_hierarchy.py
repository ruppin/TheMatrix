#!/usr/bin/env python3
"""
Example: Extract GitLab epic hierarchy to SQLite database.

This script demonstrates how to use the HierarchyExtractor to:
1. Connect to GitLab
2. Traverse an epic hierarchy
3. Store results in SQLite database
4. Display statistics

Usage:
    python extract_hierarchy.py --group-id 123 --epic-iid 10
"""

import os
import sys
from datetime import date
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitlab_hierarchy import HierarchyExtractor


def main():
    """Main extraction script."""
    # Configuration
    GITLAB_URL = os.getenv('GITLAB_URL', 'https://gitlab.com')
    GITLAB_TOKEN = os.getenv('GITLAB_TOKEN')
    GROUP_ID = int(os.getenv('GROUP_ID', '123'))
    EPIC_IID = int(os.getenv('EPIC_IID', '1'))
    DB_PATH = os.getenv('DB_PATH', 'hierarchy.db')
    MAX_DEPTH = int(os.getenv('MAX_DEPTH', '10'))
    INCLUDE_CLOSED = os.getenv('INCLUDE_CLOSED', 'true').lower() == 'true'

    if not GITLAB_TOKEN:
        print("Error: GITLAB_TOKEN environment variable is required")
        print("Set it with: export GITLAB_TOKEN='your-token-here'")
        sys.exit(1)

    print(f"GitLab Hierarchy Extractor")
    print(f"=" * 60)
    print(f"GitLab URL:      {GITLAB_URL}")
    print(f"Group ID:        {GROUP_ID}")
    print(f"Epic IID:        {EPIC_IID}")
    print(f"Database:        {DB_PATH}")
    print(f"Max Depth:       {MAX_DEPTH}")
    print(f"Include Closed:  {INCLUDE_CLOSED}")
    print(f"=" * 60)
    print()

    # Create extractor
    print("Initializing extractor...")
    with HierarchyExtractor(
        gitlab_url=GITLAB_URL,
        token=GITLAB_TOKEN,
        db_path=DB_PATH
    ) as extractor:

        # Extract hierarchy
        print(f"Extracting hierarchy from epic {GROUP_ID}#{EPIC_IID}...")
        stats = extractor.extract(
            group_id=GROUP_ID,
            epic_iid=EPIC_IID,
            max_depth=MAX_DEPTH,
            include_closed=INCLUDE_CLOSED,
            snapshot_date=date.today(),
            verbose=True
        )

        # Display results
        print()
        print("Extraction Complete!")
        print(f"=" * 60)
        print(f"Total Items:     {stats['total_items']}")
        print(f"Epics:           {stats['epic_count']}")
        print(f"Issues:          {stats['issue_count']}")
        print(f"Open:            {stats['open_count']}")
        print(f"Closed:          {stats['closed_count']}")
        print(f"Max Depth:       {stats['max_depth']}")
        print(f"=" * 60)
        print()
        print(f"Data saved to: {DB_PATH}")
        print()
        print("Next steps:")
        print(f"  - View stats:   neo stats --db {DB_PATH}")
        print(f"  - Export CSV:   neo export --db {DB_PATH} --format csv --output data.csv")
        print(f"  - Run queries:  neo query --db {DB_PATH} \"SELECT * FROM gitlab_hierarchy LIMIT 10\"")


if __name__ == '__main__':
    main()
