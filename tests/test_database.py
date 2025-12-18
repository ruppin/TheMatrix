"""
Tests for database operations.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import date

from gitlab_hierarchy.database import Database


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    db = Database(db_path)
    yield db

    db.close()
    Path(db_path).unlink(missing_ok=True)


def test_database_initialization(temp_db):
    """Test database schema creation."""
    assert temp_db.conn is not None

    # Check that table exists
    cursor = temp_db.conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gitlab_hierarchy'")
    assert cursor.fetchone() is not None


def test_insert_item(temp_db):
    """Test inserting a single item."""
    item = {
        'id': 'epic:123#10',
        'type': 'epic',
        'iid': 10,
        'group_id': 123,
        'title': 'Test Epic',
        'state': 'opened',
        'root_id': 'epic:123#10',
        'depth': 0,
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    temp_db.insert_item(item, date(2024, 1, 1))

    # Retrieve and verify
    retrieved = temp_db.get_item('epic:123#10')
    assert retrieved is not None
    assert retrieved['title'] == 'Test Epic'
    assert retrieved['type'] == 'epic'


def test_get_children(temp_db):
    """Test retrieving child items."""
    # Insert parent
    parent = {
        'id': 'epic:123#10',
        'type': 'epic',
        'iid': 10,
        'group_id': 123,
        'title': 'Parent Epic',
        'state': 'opened',
        'root_id': 'epic:123#10',
        'depth': 0,
        'parent_id': None,
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }
    temp_db.insert_item(parent)

    # Insert children
    for i in range(3):
        child = {
            'id': f'issue:456#{i}',
            'type': 'issue',
            'iid': i,
            'project_id': 456,
            'title': f'Child Issue {i}',
            'state': 'opened',
            'root_id': 'epic:123#10',
            'depth': 1,
            'parent_id': 'epic:123#10',
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
        }
        temp_db.insert_item(child)

    # Get children
    children = temp_db.get_children('epic:123#10')
    assert len(children) == 3
    assert all(child['parent_id'] == 'epic:123#10' for child in children)


def test_get_stats(temp_db):
    """Test statistics calculation."""
    # Insert some items
    items = [
        {
            'id': 'epic:123#10',
            'type': 'epic',
            'iid': 10,
            'group_id': 123,
            'title': 'Root Epic',
            'state': 'opened',
            'root_id': 'epic:123#10',
            'depth': 0,
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
        },
        {
            'id': 'issue:456#1',
            'type': 'issue',
            'iid': 1,
            'project_id': 456,
            'title': 'Issue 1',
            'state': 'opened',
            'root_id': 'epic:123#10',
            'depth': 1,
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
        },
        {
            'id': 'issue:456#2',
            'type': 'issue',
            'iid': 2,
            'project_id': 456,
            'title': 'Issue 2',
            'state': 'closed',
            'root_id': 'epic:123#10',
            'depth': 1,
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
        },
    ]

    for item in items:
        temp_db.insert_item(item)

    # Get stats
    stats = temp_db.get_stats()

    assert stats['total_items'] == 3
    assert stats['epic_count'] == 1
    assert stats['issue_count'] == 2
    assert stats['open_count'] == 2
    assert stats['closed_count'] == 1
    assert stats['max_depth'] == 1


def test_cleanup_old_snapshots(temp_db):
    """Test cleaning up old snapshots."""
    # Insert items with old and new snapshot dates
    item_old = {
        'id': 'epic:123#10',
        'type': 'epic',
        'iid': 10,
        'group_id': 123,
        'title': 'Old Snapshot',
        'state': 'opened',
        'root_id': 'epic:123#10',
        'depth': 0,
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }
    temp_db.insert_item(item_old, date(2020, 1, 1))
    temp_db.mark_old_snapshots_not_latest('epic:123#10')

    item_new = {
        'id': 'epic:123#10',
        'type': 'epic',
        'iid': 10,
        'group_id': 123,
        'title': 'New Snapshot',
        'state': 'opened',
        'root_id': 'epic:123#10',
        'depth': 0,
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }
    temp_db.insert_item(item_new, date.today())

    # Cleanup
    deleted = temp_db.cleanup_old_snapshots(keep_days=30)

    # Old snapshot should be deleted (not latest)
    assert deleted >= 1

    # New snapshot should remain
    latest = temp_db.get_item('epic:123#10', latest_only=True)
    assert latest['title'] == 'New Snapshot'
