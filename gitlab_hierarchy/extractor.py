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

    def extract(
        self,
        group_id: int,
        epic_iid: int,
        snapshot_date: Optional[date] = None,
        include_closed: bool = True,
        max_depth: int = 20,
        verbose: bool = False
    ) -> dict:
        """
        Extract complete hierarchy starting from a root epic.

        Args:
            group_id: Group ID of root epic
            epic_iid: IID of root epic
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
        logger.info("GitLab Hierarchy Extractor v1.0")
        logger.info("=" * 80)
        logger.info(f"Configuration:")
        logger.info(f"  GitLab URL: {self.gitlab_url}")
        logger.info(f"  Root Epic: Group {group_id}, Epic #{epic_iid}")
        logger.info(f"  Database: {self.db_path}")
        logger.info(f"  Snapshot Date: {snapshot_date}")
        logger.info(f"  Include Closed: {include_closed}")
        logger.info(f"  Max Depth: {max_depth}")
        logger.info("")

        # Phase 1: Discover hierarchy structure
        logger.info("Phase 1: Discovering hierarchy structure")
        logger.info("-" * 80)

        items = self.builder.build_from_epic(
            group_id=group_id,
            epic_iid=epic_iid,
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

        root_id = f"epic:{group_id}#{epic_iid}"
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
