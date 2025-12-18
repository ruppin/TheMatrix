"""
SQLite database operations for GitLab hierarchy storage.
"""

import sqlite3
import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

from .models import SCHEMA_SQL, INDEXES_SQL

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for GitLab hierarchy data."""

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.conn = None
        self._connect()
        self._initialize_schema()

    def _connect(self):
        """Establish database connection."""
        logger.info(f"Connecting to database: {self.db_path}")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        logger.info("Database connection established")

    def _initialize_schema(self):
        """Create tables and indexes if they don't exist."""
        logger.info("Initializing database schema")

        cursor = self.conn.cursor()

        # Create table
        cursor.execute(SCHEMA_SQL)

        # Create indexes
        for index_sql in INDEXES_SQL:
            cursor.execute(index_sql)

        self.conn.commit()
        logger.info("Database schema initialized")

    def insert_item(self, item: Dict[str, Any], snapshot_date: Optional[date] = None):
        """
        Insert a single hierarchy item.

        Args:
            item: Dictionary containing item data
            snapshot_date: Date of snapshot (defaults to today)
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        # Add snapshot date and version info
        item['snapshot_date'] = snapshot_date.isoformat()
        item['is_latest'] = 1

        # Convert lists/dicts to JSON strings
        for field in ['blocks', 'blocked_by', 'related_issues', 'related_merge_requests', 'labels_raw']:
            if field in item and isinstance(item[field], (list, dict)):
                item[field] = json.dumps(item[field])

        # Remove fields that are not in the database schema
        # internal_id is only used during traversal, not stored
        fields_to_exclude = ['internal_id']
        item_filtered = {k: v for k, v in item.items() if k not in fields_to_exclude}

        # Build INSERT statement
        columns = list(item_filtered.keys())
        placeholders = ','.join(['?' for _ in columns])
        column_names = ','.join(columns)

        sql = f"""
            INSERT OR REPLACE INTO gitlab_hierarchy ({column_names})
            VALUES ({placeholders})
        """

        cursor = self.conn.cursor()
        cursor.execute(sql, [item_filtered[col] for col in columns])
        self.conn.commit()

        logger.debug(f"Inserted item: {item.get('id')}")

    def insert_batch(self, items: List[Dict[str, Any]], snapshot_date: Optional[date] = None):
        """
        Insert multiple items in a batch.

        Args:
            items: List of item dictionaries
            snapshot_date: Date of snapshot (defaults to today)
        """
        if not items:
            return

        logger.info(f"Batch inserting {len(items)} items")

        for item in items:
            self.insert_item(item, snapshot_date)

        logger.info(f"Batch insert completed: {len(items)} items")

    def mark_old_snapshots_not_latest(self, item_id: str):
        """
        Mark previous snapshots of an item as not latest.

        Args:
            item_id: Item ID to update
        """
        sql = """
            UPDATE gitlab_hierarchy
            SET is_latest = 0
            WHERE id = ? AND is_latest = 1
        """
        cursor = self.conn.cursor()
        cursor.execute(sql, (item_id,))
        self.conn.commit()

    def get_latest_snapshot_date(self, root_id: Optional[str] = None) -> Optional[date]:
        """
        Get the most recent snapshot date.

        Args:
            root_id: Optional root ID to filter by

        Returns:
            Most recent snapshot date or None
        """
        if root_id:
            sql = """
                SELECT MAX(snapshot_date) as max_date
                FROM gitlab_hierarchy
                WHERE root_id = ?
            """
            cursor = self.conn.cursor()
            cursor.execute(sql, (root_id,))
        else:
            sql = """
                SELECT MAX(snapshot_date) as max_date
                FROM gitlab_hierarchy
            """
            cursor = self.conn.cursor()
            cursor.execute(sql)

        row = cursor.fetchone()
        if row and row['max_date']:
            return date.fromisoformat(row['max_date'])
        return None

    def get_item(self, item_id: str, latest_only: bool = True) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single item by ID.

        Args:
            item_id: Item ID to retrieve
            latest_only: Only get latest snapshot (default: True)

        Returns:
            Item dictionary or None
        """
        if latest_only:
            sql = """
                SELECT * FROM gitlab_hierarchy
                WHERE id = ? AND is_latest = 1
            """
        else:
            sql = """
                SELECT * FROM gitlab_hierarchy
                WHERE id = ?
                ORDER BY snapshot_date DESC
                LIMIT 1
            """

        cursor = self.conn.cursor()
        cursor.execute(sql, (item_id,))
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def get_children(self, parent_id: str, latest_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all direct children of a parent item.

        Args:
            parent_id: Parent item ID
            latest_only: Only get latest snapshots (default: True)

        Returns:
            List of child item dictionaries
        """
        if latest_only:
            sql = """
                SELECT * FROM gitlab_hierarchy
                WHERE parent_id = ? AND is_latest = 1
                ORDER BY sibling_position, iid
            """
        else:
            sql = """
                SELECT * FROM gitlab_hierarchy
                WHERE parent_id = ?
                ORDER BY snapshot_date DESC, sibling_position, iid
            """

        cursor = self.conn.cursor()
        cursor.execute(sql, (parent_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_root_items(self, latest_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all root items (depth = 0).

        Args:
            latest_only: Only get latest snapshots (default: True)

        Returns:
            List of root item dictionaries
        """
        if latest_only:
            sql = """
                SELECT * FROM gitlab_hierarchy
                WHERE depth = 0 AND is_latest = 1
                ORDER BY created_at DESC
            """
        else:
            sql = """
                SELECT * FROM gitlab_hierarchy
                WHERE depth = 0
                ORDER BY snapshot_date DESC, created_at DESC
            """

        cursor = self.conn.cursor()
        cursor.execute(sql)
        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self, root_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about stored data.

        Args:
            root_id: Optional root ID to filter by

        Returns:
            Statistics dictionary
        """
        where_clause = "WHERE is_latest = 1"
        params = []

        if root_id:
            where_clause += " AND root_id = ?"
            params.append(root_id)

        sql = f"""
            SELECT
                COUNT(*) as total_items,
                COUNT(*) FILTER (WHERE type = 'epic') as epic_count,
                COUNT(*) FILTER (WHERE type = 'issue') as issue_count,
                COUNT(*) FILTER (WHERE state = 'opened') as open_count,
                COUNT(*) FILTER (WHERE state = 'closed') as closed_count,
                MAX(depth) as max_depth,
                AVG(depth) as avg_depth,
                COUNT(*) FILTER (WHERE is_leaf = 1) as leaf_count,
                COUNT(DISTINCT root_id) as root_count,
                MIN(snapshot_date) as first_snapshot,
                MAX(snapshot_date) as last_snapshot
            FROM gitlab_hierarchy
            {where_clause}
        """

        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()

        return dict(row) if row else {}

    def cleanup_old_snapshots(self, keep_days: int = 90):
        """
        Remove snapshots older than specified days.

        Args:
            keep_days: Number of days to keep (default: 90)
        """
        from datetime import datetime, timedelta

        cutoff_date = (datetime.now() - timedelta(days=keep_days)).date()

        sql = """
            DELETE FROM gitlab_hierarchy
            WHERE snapshot_date < ? AND is_latest = 0
        """

        cursor = self.conn.cursor()
        cursor.execute(sql, (cutoff_date.isoformat(),))
        deleted_count = cursor.rowcount
        self.conn.commit()

        logger.info(f"Cleaned up {deleted_count} old snapshots (kept last {keep_days} days)")
        return deleted_count

    def execute_query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute a custom SQL query.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
