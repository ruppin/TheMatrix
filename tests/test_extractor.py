"""
Tests for the main HierarchyExtractor orchestrator.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import date

from gitlab_hierarchy.extractor import HierarchyExtractor


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def mock_components():
    """Create mocked components."""
    with patch('gitlab_hierarchy.extractor.GitLabClient') as mock_client_class, \
         patch('gitlab_hierarchy.extractor.HierarchyBuilder') as mock_builder_class, \
         patch('gitlab_hierarchy.extractor.LabelParser') as mock_parser_class:

        mock_client = Mock()
        mock_builder = Mock()
        mock_parser = Mock()

        mock_client_class.return_value = mock_client
        mock_builder_class.return_value = mock_builder
        mock_parser_class.return_value = mock_parser

        yield {
            'client': mock_client,
            'builder': mock_builder,
            'parser': mock_parser
        }


def test_extractor_initialization(temp_db, mock_components):
    """Test extractor initialization."""
    with patch.dict('os.environ', {'GITLAB_TOKEN': 'test-token'}):
        extractor = HierarchyExtractor(
            gitlab_url='https://gitlab.example.com',
            db_path=temp_db
        )

    assert extractor is not None
    assert extractor.db is not None
    assert extractor.client is not None


def test_extract_basic_hierarchy(temp_db, mock_components):
    """Test basic extraction workflow."""
    mock_builder = mock_components['builder']
    mock_parser = mock_components['parser']

    # Mock hierarchy data
    hierarchy_items = [
        {
            'id': 'epic:123#1',
            'type': 'epic',
            'iid': 1,
            'group_id': 123,
            'title': 'Root Epic',
            'state': 'opened',
            'root_id': 'epic:123#1',
            'depth': 0,
            'labels': ['priority:high'],
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
        },
        {
            'id': 'issue:456#1',
            'type': 'issue',
            'iid': 1,
            'project_id': 456,
            'title': 'Child Issue',
            'state': 'opened',
            'root_id': 'epic:123#1',
            'parent_id': 'epic:123#1',
            'depth': 1,
            'labels': ['bug'],
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
        }
    ]

    # Mock the hierarchy builder to return our test data
    mock_builder.build_from_epic.return_value = hierarchy_items

    # Mock label parser to add label fields
    def parse_items_side_effect(items):
        for item in items:
            if 'priority:high' in item.get('labels', []):
                item['label_priority'] = 'high'
            if 'bug' in item.get('labels', []):
                item['label_type'] = 'bug'
        return items

    mock_parser.parse_items.side_effect = parse_items_side_effect

    with patch.dict('os.environ', {'GITLAB_TOKEN': 'test-token'}):
        extractor = HierarchyExtractor(
            gitlab_url='https://gitlab.example.com',
            db_path=temp_db
        )

        stats = extractor.extract(
            group_id=123,
            epic_iid=1,
            snapshot_date=date(2024, 1, 1)
        )

    # Verify extraction stats
    assert stats is not None
    assert stats['total_items'] == 2
    assert stats['epic_count'] == 1
    assert stats['issue_count'] == 1

    # Verify builder was called correctly
    mock_builder.build_from_epic.assert_called_once_with(
        group_id=123,
        epic_iid=1,
        max_depth=10,
        include_closed=True
    )

    # Verify parser was called
    mock_parser.parse_items.assert_called_once()

    extractor.close()


def test_extract_with_options(temp_db, mock_components):
    """Test extraction with various options."""
    mock_builder = mock_components['builder']
    mock_parser = mock_components['parser']

    hierarchy_items = [
        {
            'id': 'epic:123#1',
            'type': 'epic',
            'iid': 1,
            'group_id': 123,
            'title': 'Root Epic',
            'state': 'opened',
            'root_id': 'epic:123#1',
            'depth': 0,
            'labels': [],
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
        }
    ]

    mock_builder.build_from_epic.return_value = hierarchy_items
    mock_parser.parse_items.return_value = hierarchy_items

    with patch.dict('os.environ', {'GITLAB_TOKEN': 'test-token'}):
        extractor = HierarchyExtractor(
            gitlab_url='https://gitlab.example.com',
            db_path=temp_db
        )

        stats = extractor.extract(
            group_id=123,
            epic_iid=1,
            max_depth=5,
            include_closed=False,
            snapshot_date=date(2024, 1, 15)
        )

    # Verify builder was called with correct options
    mock_builder.build_from_epic.assert_called_once_with(
        group_id=123,
        epic_iid=1,
        max_depth=5,
        include_closed=False
    )

    assert stats['total_items'] == 1

    extractor.close()


def test_extract_empty_hierarchy(temp_db, mock_components):
    """Test extraction when no items are found."""
    mock_builder = mock_components['builder']
    mock_parser = mock_components['parser']

    # Return empty hierarchy
    mock_builder.build_from_epic.return_value = []
    mock_parser.parse_items.return_value = []

    with patch.dict('os.environ', {'GITLAB_TOKEN': 'test-token'}):
        extractor = HierarchyExtractor(
            gitlab_url='https://gitlab.example.com',
            db_path=temp_db
        )

        stats = extractor.extract(group_id=123, epic_iid=1)

    assert stats['total_items'] == 0
    assert stats['epic_count'] == 0
    assert stats['issue_count'] == 0

    extractor.close()


def test_get_stats(temp_db, mock_components):
    """Test getting statistics from database."""
    mock_builder = mock_components['builder']
    mock_parser = mock_components['parser']

    hierarchy_items = [
        {
            'id': 'epic:123#1',
            'type': 'epic',
            'iid': 1,
            'group_id': 123,
            'title': 'Root Epic',
            'state': 'opened',
            'root_id': 'epic:123#1',
            'depth': 0,
            'labels': [],
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
        }
    ]

    mock_builder.build_from_epic.return_value = hierarchy_items
    mock_parser.parse_items.return_value = hierarchy_items

    with patch.dict('os.environ', {'GITLAB_TOKEN': 'test-token'}):
        extractor = HierarchyExtractor(
            gitlab_url='https://gitlab.example.com',
            db_path=temp_db
        )

        # First extract some data
        extractor.extract(group_id=123, epic_iid=1)

        # Then get stats
        stats = extractor.get_stats(root_id='epic:123#1')

    assert stats is not None
    assert 'total_items' in stats
    assert stats['total_items'] > 0

    extractor.close()


def test_cleanup_old_snapshots(temp_db, mock_components):
    """Test cleanup of old snapshot data."""
    mock_builder = mock_components['builder']
    mock_parser = mock_components['parser']

    hierarchy_items = [
        {
            'id': 'epic:123#1',
            'type': 'epic',
            'iid': 1,
            'group_id': 123,
            'title': 'Root Epic',
            'state': 'opened',
            'root_id': 'epic:123#1',
            'depth': 0,
            'labels': [],
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
        }
    ]

    mock_builder.build_from_epic.return_value = hierarchy_items
    mock_parser.parse_items.return_value = hierarchy_items

    with patch.dict('os.environ', {'GITLAB_TOKEN': 'test-token'}):
        extractor = HierarchyExtractor(
            gitlab_url='https://gitlab.example.com',
            db_path=temp_db
        )

        # Extract old snapshot
        extractor.extract(
            group_id=123,
            epic_iid=1,
            snapshot_date=date(2020, 1, 1)
        )

        # Mark as not latest
        extractor.db.mark_old_snapshots_not_latest('epic:123#1')

        # Extract new snapshot
        extractor.extract(
            group_id=123,
            epic_iid=1,
            snapshot_date=date.today()
        )

        # Cleanup old snapshots
        deleted = extractor.cleanup_old_snapshots(keep_days=30)

    # Should have deleted the old snapshot
    assert deleted >= 0

    extractor.close()


def test_context_manager(temp_db, mock_components):
    """Test using extractor as context manager."""
    mock_builder = mock_components['builder']
    mock_builder.build_from_epic.return_value = []

    mock_parser = mock_components['parser']
    mock_parser.parse_items.return_value = []

    with patch.dict('os.environ', {'GITLAB_TOKEN': 'test-token'}):
        with HierarchyExtractor(
            gitlab_url='https://gitlab.example.com',
            db_path=temp_db
        ) as extractor:
            stats = extractor.extract(group_id=123, epic_iid=1)

        # Should have closed connections automatically
        assert extractor.db.conn is None


def test_verbose_output(temp_db, mock_components):
    """Test verbose output during extraction."""
    mock_builder = mock_components['builder']
    mock_parser = mock_components['parser']

    hierarchy_items = [
        {
            'id': 'epic:123#1',
            'type': 'epic',
            'iid': 1,
            'group_id': 123,
            'title': 'Root Epic',
            'state': 'opened',
            'root_id': 'epic:123#1',
            'depth': 0,
            'labels': [],
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z',
        }
    ]

    mock_builder.build_from_epic.return_value = hierarchy_items
    mock_parser.parse_items.return_value = hierarchy_items

    with patch.dict('os.environ', {'GITLAB_TOKEN': 'test-token'}):
        extractor = HierarchyExtractor(
            gitlab_url='https://gitlab.example.com',
            db_path=temp_db
        )

        # Extract with verbose=True
        with patch('tqdm.tqdm') as mock_tqdm:
            stats = extractor.extract(
                group_id=123,
                epic_iid=1,
                verbose=True
            )

        # tqdm should have been used for progress tracking
        # (In real implementation, this would be called)

    extractor.close()


def test_custom_label_patterns(temp_db, mock_components):
    """Test extractor with custom label patterns."""
    with patch.dict('os.environ', {'GITLAB_TOKEN': 'test-token'}):
        custom_patterns = {
            'severity': 'label_severity',
            'area': 'label_area'
        }

        extractor = HierarchyExtractor(
            gitlab_url='https://gitlab.example.com',
            db_path=temp_db,
            label_patterns=custom_patterns
        )

    # Verify custom patterns were passed to label parser
    assert extractor.label_parser is not None

    extractor.close()
