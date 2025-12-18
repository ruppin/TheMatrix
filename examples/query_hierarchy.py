#!/usr/bin/env python3
"""
Example: Query GitLab hierarchy database.

This script demonstrates various SQL queries you can run against
the extracted hierarchy data.

Usage:
    python query_hierarchy.py
"""

import os
import sys
from pathlib import Path
import sqlite3
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gitlab_hierarchy import Database


def print_header(title):
    """Print a formatted header."""
    print()
    print(f"{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")
    print()


def run_query(db, title, query):
    """Run a query and display results."""
    print_header(title)
    print(f"Query: {query}")
    print()

    results = db.execute_query(query)

    if not results:
        print("No results found.")
        return

    # Convert to DataFrame for nice display
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    print(f"\n({len(results)} rows)")


def main():
    """Main query demonstration."""
    DB_PATH = os.getenv('DB_PATH', 'hierarchy.db')

    if not Path(DB_PATH).exists():
        print(f"Error: Database not found at {DB_PATH}")
        print("Run extract_hierarchy.py first to create the database.")
        sys.exit(1)

    print(f"Querying GitLab Hierarchy Database: {DB_PATH}")

    with Database(DB_PATH) as db:

        # Query 1: Overview statistics
        run_query(
            db,
            "1. Overview Statistics",
            """
            SELECT
                COUNT(*) as total_items,
                SUM(CASE WHEN type = 'epic' THEN 1 ELSE 0 END) as epics,
                SUM(CASE WHEN type = 'issue' THEN 1 ELSE 0 END) as issues,
                SUM(CASE WHEN state = 'opened' THEN 1 ELSE 0 END) as open,
                SUM(CASE WHEN state = 'closed' THEN 1 ELSE 0 END) as closed,
                MAX(depth) as max_depth
            FROM gitlab_hierarchy
            WHERE is_latest = 1
            """
        )

        # Query 2: Top-level epics
        run_query(
            db,
            "2. Top-Level Epics (Depth 0)",
            """
            SELECT
                id,
                title,
                state,
                child_epic_count,
                child_issue_count,
                created_at
            FROM gitlab_hierarchy
            WHERE depth = 0 AND type = 'epic' AND is_latest = 1
            ORDER BY created_at DESC
            """
        )

        # Query 3: Issues by priority
        run_query(
            db,
            "3. Issues Grouped by Priority",
            """
            SELECT
                COALESCE(label_priority, 'none') as priority,
                COUNT(*) as count,
                SUM(CASE WHEN state = 'opened' THEN 1 ELSE 0 END) as open,
                SUM(CASE WHEN state = 'closed' THEN 1 ELSE 0 END) as closed
            FROM gitlab_hierarchy
            WHERE type = 'issue' AND is_latest = 1
            GROUP BY label_priority
            ORDER BY
                CASE label_priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5
                END
            """
        )

        # Query 4: Overdue items
        run_query(
            db,
            "4. Overdue Items",
            """
            SELECT
                id,
                type,
                title,
                due_date,
                days_open,
                assignee_username,
                label_priority
            FROM gitlab_hierarchy
            WHERE is_overdue = 1 AND state = 'opened' AND is_latest = 1
            ORDER BY due_date ASC
            LIMIT 20
            """
        )

        # Query 5: Most complex epics (by child count)
        run_query(
            db,
            "5. Most Complex Epics (by Children)",
            """
            SELECT
                id,
                title,
                state,
                child_epic_count,
                child_issue_count,
                (child_epic_count + child_issue_count) as total_children,
                depth
            FROM gitlab_hierarchy
            WHERE type = 'epic' AND is_latest = 1
            ORDER BY total_children DESC
            LIMIT 10
            """
        )

        # Query 6: Issues by type/label
        run_query(
            db,
            "6. Issues by Type",
            """
            SELECT
                COALESCE(label_type, 'none') as type,
                COUNT(*) as count,
                ROUND(AVG(days_open), 1) as avg_days_open,
                ROUND(AVG(weight), 1) as avg_weight
            FROM gitlab_hierarchy
            WHERE type = 'issue' AND state = 'opened' AND is_latest = 1
            GROUP BY label_type
            ORDER BY count DESC
            """
        )

        # Query 7: Hierarchy depth analysis
        run_query(
            db,
            "7. Items by Hierarchy Depth",
            """
            SELECT
                depth,
                COUNT(*) as count,
                SUM(CASE WHEN type = 'epic' THEN 1 ELSE 0 END) as epics,
                SUM(CASE WHEN type = 'issue' THEN 1 ELSE 0 END) as issues
            FROM gitlab_hierarchy
            WHERE is_latest = 1
            GROUP BY depth
            ORDER BY depth
            """
        )

        # Query 8: Recently updated items
        run_query(
            db,
            "8. Recently Updated Items (Last 30 Days)",
            """
            SELECT
                id,
                type,
                title,
                state,
                updated_at,
                assignee_username
            FROM gitlab_hierarchy
            WHERE
                is_latest = 1
                AND updated_at >= date('now', '-30 days')
            ORDER BY updated_at DESC
            LIMIT 20
            """
        )

        # Query 9: Blocked issues
        run_query(
            db,
            "9. Blocked Issues",
            """
            SELECT
                id,
                title,
                state,
                blocked_by_count,
                label_priority,
                assignee_username
            FROM gitlab_hierarchy
            WHERE
                type = 'issue'
                AND blocked_by_count > 0
                AND state = 'opened'
                AND is_latest = 1
            ORDER BY blocked_by_count DESC, label_priority
            LIMIT 20
            """
        )

        # Query 10: Completion analysis by epic
        run_query(
            db,
            "10. Epic Completion Rates",
            """
            SELECT
                id,
                title,
                child_issue_count,
                ROUND(completion_pct, 1) as completion_pct,
                state
            FROM gitlab_hierarchy
            WHERE
                type = 'epic'
                AND child_issue_count > 0
                AND is_latest = 1
            ORDER BY completion_pct DESC
            LIMIT 15
            """
        )

    print()
    print("=" * 80)
    print("Query examples complete!")
    print()
    print("You can also run custom queries using:")
    print(f'  neo query --db {DB_PATH} "YOUR SQL HERE"')
    print()


if __name__ == '__main__':
    main()
