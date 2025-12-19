"""
Main hierarchy extraction orchestrator.
"""

import logging
import time
from datetime import date
from typing import Optional
from tqdm import tqdm

from .gitlab_client import GitLabClient
from .hierarchy_builder import HierarchyBuilder
from .label_parser import LabelParser
from .database import Database

logger = logging.getLogger(__name__)


class HierarchyExtractor:
    """Main orchestrator for GitLab hierarchy extraction."""

    def __init__(
        self,
        gitlab_url: str,
        token: str,
        db_path: str,
        **kwargs
    ):
        """
        Initialize extractor.

        Args:
            gitlab_url: GitLab instance URL
            token: Personal access token
            db_path: Path to SQLite database
            **kwargs: Additional configuration options
        """
        self.gitlab_url = gitlab_url
        self.db_path = db_path

        # Initialize components
        logger.info("Initializing GitLab Hierarchy Extractor")

        self.client = GitLabClient(
            gitlab_url=gitlab_url,
            token=token,
            timeout=kwargs.get('timeout', 30),
            max_retries=kwargs.get('max_retries', 3),
            rate_limit_delay=kwargs.get('rate_limit_delay', 0.5)
        )

        self.builder = HierarchyBuilder(self.client)
        self.label_parser = LabelParser(patterns=kwargs.get('label_patterns'))
        self.db = Database(db_path)

        logger.info("✓ Extractor initialized")

    def extract_from_groups(
        self,
        group_ids: list,
        root_group_id: int,
        root_epic_iid: int,
        snapshot_date: Optional[date] = None,
        include_closed: bool = True,
        max_depth: int = 20,
        verbose: bool = False
    ) -> dict:
        """
        Extract hierarchy using in-memory method by fetching all epics upfront.

        This method is more reliable when GitLab's parent_id filter doesn't work
        correctly. It fetches all epics from the specified groups and builds the
        hierarchy in-memory using parent_epic_id relationships.

        Args:
            group_ids: List of group IDs to fetch epics from
            root_group_id: Group ID containing the root epic
            root_epic_iid: IID of the root epic
            snapshot_date: Date of snapshot (defaults to today)
            include_closed: Include closed items
            max_depth: Maximum depth to traverse
            verbose: Show progress bars

        Returns:
            Summary statistics dictionary
        """
        start_time = time.time()

        if snapshot_date is None:
            snapshot_date = date.today()

        logger.info("=" * 80)
        logger.info("GitLab Hierarchy Extractor v1.0 (In-Memory Method)")
        logger.info("=" * 80)
        logger.info(f"Configuration:")
        logger.info(f"  GitLab URL: {self.gitlab_url}")
        logger.info(f"  Root Epic: Group {root_group_id}, Epic #{root_epic_iid}")
        logger.info(f"  Group IDs: {group_ids}")
        logger.info(f"  Database: {self.db_path}")
        logger.info(f"  Snapshot Date: {snapshot_date}")
        logger.info(f"  Include Closed: {include_closed}")
        logger.info(f"  Max Depth: {max_depth}")
        logger.info("")

        # Phase 1: Discover hierarchy structure using in-memory method
        logger.info("Phase 1: Discovering hierarchy structure (in-memory method)")
        logger.info("-" * 80)

        items = self.builder.build_from_groups(
            group_ids=group_ids,
            root_group_id=root_group_id,
            root_epic_iid=root_epic_iid,
            max_depth=max_depth,
            include_closed=include_closed
        )

        epic_count = sum(1 for item in items if item['type'] == 'epic')
        issue_count = sum(1 for item in items if item['type'] == 'issue')

        logger.info(f"✓ Total epics discovered: {epic_count}")
        logger.info(f"✓ Total issues discovered: {issue_count}")
        logger.info("")

        # Phase 2: Parse labels
        logger.info("Phase 2: Parsing labels")
        logger.info("-" * 80)

        items = self.label_parser.parse_items(items)
        categories = self.label_parser.get_discovered_categories()

        logger.info(f"✓ Parsed labels for {len(items)} items")
        if categories:
            logger.info(f"✓ Detected custom categories: {', '.join(sorted(categories))}")
        logger.info("")

        # Phase 3: Store to database
        logger.info("Phase 3: Storing to database")
        logger.info("-" * 80)

        if verbose:
            items_iter = tqdm(items, desc="Inserting items", unit="item")
        else:
            items_iter = items

        for item in items_iter:
            self.db.insert_item(item, snapshot_date)

        logger.info(f"✓ Inserted {len(items)} total items")
        logger.info(f"  - Epics: {epic_count}")
        logger.info(f"  - Issues: {issue_count}")
        logger.info("")

        # Phase 4: Calculate statistics
        logger.info("Phase 4: Calculating statistics")
        logger.info("-" * 80)

        root_id = f"epic:{root_group_id}#{root_epic_iid}"
        stats = self.db.get_stats(root_id=root_id)

        open_count = stats.get('open_count', 0)
        closed_count = stats.get('closed_count', 0)
        max_depth_val = stats.get('max_depth', 0)
        avg_depth_val = stats.get('avg_depth', 0)
        leaf_count = stats.get('leaf_count', 0)

        logger.info(f"✓ Statistics calculated")
        logger.info("")

        # Summary
        elapsed = time.time() - start_time

        logger.info("=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Items: {len(items)}")
        logger.info(f"  Epics: {epic_count}")
        logger.info(f"  Issues: {issue_count}")
        logger.info(f"Open: {open_count} ({open_count/len(items)*100:.1f}%)")
        logger.info(f"Closed: {closed_count} ({closed_count/len(items)*100:.1f}%)")
        logger.info(f"Max Depth: {max_depth_val} levels")
        logger.info(f"Avg Depth: {avg_depth_val:.1f} levels")
        logger.info(f"Leaf Nodes: {leaf_count}")
        logger.info("")
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Execution Time: {elapsed:.2f}s ({elapsed/60:.2f} minutes)")
        logger.info("=" * 80)
        logger.info("✓ Extraction complete!")
        logger.info("=" * 80)

        return {
            'success': True,
            'total_items': len(items),
            'epic_count': epic_count,
            'issue_count': issue_count,
            'open_count': open_count,
            'closed_count': closed_count,
            'max_depth': max_depth_val,
            'avg_depth': avg_depth_val,
            'leaf_count': leaf_count,
            'execution_time': elapsed,
            'snapshot_date': snapshot_date.isoformat(),
        }

    def extract_issues_from_groups(
        self,
        group_ids: list,
        snapshot_date: Optional[date] = None,
        include_closed: bool = True,
        verbose: bool = False
    ) -> dict:
        """
        Extract all issues from all projects in specified groups.

        This method fetches ALL issues from all projects (not just epic-linked ones)
        and stores them in the gitlab_project_issues table with epic linkage information.

        Args:
            group_ids: List of group IDs to fetch projects/issues from
            snapshot_date: Date of snapshot (defaults to today)
            include_closed: Include closed items
            verbose: Show progress bars

        Returns:
            Summary statistics dictionary
        """
        start_time = time.time()

        if snapshot_date is None:
            snapshot_date = date.today()

        logger.info("=" * 80)
        logger.info("GitLab Project Issues Extractor v1.0")
        logger.info("=" * 80)
        logger.info(f"Configuration:")
        logger.info(f"  GitLab URL: {self.gitlab_url}")
        logger.info(f"  Group IDs: {group_ids}")
        logger.info(f"  Database: {self.db_path}")
        logger.info(f"  Snapshot Date: {snapshot_date}")
        logger.info(f"  Include Closed: {include_closed}")
        logger.info("")

        # Phase 1: Fetch all issues from all projects
        logger.info("Phase 1: Fetching all issues from projects")
        logger.info("-" * 80)

        all_issues = self.client.get_all_issues_for_groups(group_ids)

        if not include_closed:
            all_issues = [issue for issue in all_issues if issue['state'] != 'closed']

        logger.info(f"✓ Total issues fetched: {len(all_issues)}")

        # Calculate statistics
        epic_linked_count = sum(1 for issue in all_issues if issue.get('epic_id'))
        orphan_count = len(all_issues) - epic_linked_count
        open_count = sum(1 for issue in all_issues if issue['state'] == 'opened')
        closed_count = sum(1 for issue in all_issues if issue['state'] == 'closed')

        logger.info(f"  - Linked to epics: {epic_linked_count}")
        logger.info(f"  - Not linked to epics: {orphan_count}")
        logger.info(f"  - Open: {open_count}")
        logger.info(f"  - Closed: {closed_count}")
        logger.info("")

        # Phase 2: Parse labels
        logger.info("Phase 2: Parsing labels")
        logger.info("-" * 80)

        all_issues = self.label_parser.parse_items(all_issues)
        categories = self.label_parser.get_discovered_categories()

        logger.info(f"✓ Parsed labels for {len(all_issues)} issues")
        if categories:
            logger.info(f"✓ Detected custom categories: {', '.join(sorted(categories))}")
        logger.info("")

        # Phase 3: Calculate metrics
        logger.info("Phase 3: Calculating metrics")
        logger.info("-" * 80)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        for issue in all_issues:
            # Parse dates
            created_at = self._parse_datetime(issue.get('created_at'))
            closed_at = self._parse_datetime(issue.get('closed_at'))
            due_date = self._parse_date(issue.get('due_date'))

            # Calculate days open
            if issue['state'] == 'opened' and created_at:
                issue['days_open'] = (now - created_at).days
            else:
                issue['days_open'] = None

            # Calculate days to close
            if closed_at and created_at:
                issue['days_to_close'] = (closed_at - created_at).days
            else:
                issue['days_to_close'] = None

            # Calculate overdue
            if due_date and issue['state'] == 'opened':
                issue['is_overdue'] = 1 if due_date < now.date() else 0
                if issue['is_overdue']:
                    issue['days_overdue'] = (now.date() - due_date).days
                else:
                    issue['days_overdue'] = None
            else:
                issue['is_overdue'] = 0
                issue['days_overdue'] = None

        logger.info(f"✓ Metrics calculated")
        logger.info("")

        # Phase 4: Store to database
        logger.info("Phase 4: Storing to database")
        logger.info("-" * 80)

        if verbose:
            issues_iter = tqdm(all_issues, desc="Inserting issues", unit="issue")
        else:
            issues_iter = all_issues

        for issue in issues_iter:
            self.db.insert_project_issue(issue, snapshot_date)

        logger.info(f"✓ Inserted {len(all_issues)} total issues")
        logger.info(f"  - Linked to epics: {epic_linked_count}")
        logger.info(f"  - Orphan issues: {orphan_count}")
        logger.info("")

        # Summary
        elapsed = time.time() - start_time

        logger.info("=" * 80)
        logger.info("SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Issues: {len(all_issues)}")
        logger.info(f"  Open: {open_count} ({open_count/len(all_issues)*100:.1f}%)" if all_issues else "  Open: 0")
        logger.info(f"  Closed: {closed_count} ({closed_count/len(all_issues)*100:.1f}%)" if all_issues else "  Closed: 0")
        logger.info(f"Epic Linked: {epic_linked_count} ({epic_linked_count/len(all_issues)*100:.1f}%)" if all_issues else "Epic Linked: 0")
        logger.info(f"Orphan Issues: {orphan_count} ({orphan_count/len(all_issues)*100:.1f}%)" if all_issues else "Orphan Issues: 0")
        logger.info("")
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Table: gitlab_project_issues")
        logger.info(f"Execution Time: {elapsed:.2f}s ({elapsed/60:.2f} minutes)")
        logger.info("=" * 80)
        logger.info("✓ Extraction complete!")
        logger.info("=" * 80)

        return {
            'success': True,
            'total_issues': len(all_issues),
            'epic_linked_count': epic_linked_count,
            'orphan_count': orphan_count,
            'open_count': open_count,
            'closed_count': closed_count,
            'execution_time': elapsed,
            'snapshot_date': snapshot_date.isoformat(),
        }

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not dt_str:
            return None
        try:
            from datetime import datetime
            if '.' in dt_str:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except Exception:
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse ISO date string."""
        if not date_str:
            return None
        try:
            from datetime import datetime
            return datetime.fromisoformat(date_str).date()
        except Exception:
            return None

    def get_stats(self, root_id: Optional[str] = None) -> dict:
        """
        Get statistics from database.

        Args:
            root_id: Optional root ID to filter by

        Returns:
            Statistics dictionary
        """
        return self.db.get_stats(root_id)

    def cleanup_old_snapshots(self, keep_days: int = 90) -> int:
        """
        Remove old snapshots from database.

        Args:
            keep_days: Number of days to keep

        Returns:
            Number of snapshots deleted
        """
        logger.info(f"Cleaning up snapshots older than {keep_days} days")
        deleted = self.db.cleanup_old_snapshots(keep_days)
        logger.info(f"✓ Removed {deleted} old snapshots")
        return deleted

    def close(self):
        """Close connections."""
        self.db.close()
