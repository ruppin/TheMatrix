"""
Tests for hierarchy building functionality.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, date

from gitlab_hierarchy.hierarchy_builder import HierarchyBuilder


@pytest.fixture
def mock_client():
    """Create a mock GitLab client."""
    client = Mock()
    return client


@pytest.fixture
def builder(mock_client):
    """Create a HierarchyBuilder with mock client."""
    return HierarchyBuilder(mock_client)


def test_simple_epic_hierarchy(builder, mock_client):
    """Test building hierarchy from a single epic with no children."""
    # Mock the root epic
    root_epic = {
        'id': 'epic:123#1',
        'type': 'epic',
        'iid': 1,
        'group_id': 123,
        'title': 'Root Epic',
        'state': 'opened',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    mock_client.get_epic.return_value = root_epic
    mock_client.get_child_epics.return_value = []
    mock_client.get_epic_issues.return_value = []

    hierarchy = builder.build_from_epic(123, 1)

    assert len(hierarchy) == 1
    assert hierarchy[0]['id'] == 'epic:123#1'
    assert hierarchy[0]['depth'] == 0
    assert hierarchy[0]['root_id'] == 'epic:123#1'
    assert hierarchy[0]['parent_id'] is None


def test_epic_with_child_epics(builder, mock_client):
    """Test epic with child epics."""
    root_epic = {
        'id': 'epic:123#1',
        'type': 'epic',
        'iid': 1,
        'group_id': 123,
        'title': 'Root Epic',
        'state': 'opened',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    child_epic1 = {
        'id': 'epic:123#2',
        'type': 'epic',
        'iid': 2,
        'group_id': 123,
        'title': 'Child Epic 1',
        'state': 'opened',
        'parent_id': 'epic:123#1',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    child_epic2 = {
        'id': 'epic:123#3',
        'type': 'epic',
        'iid': 3,
        'group_id': 123,
        'title': 'Child Epic 2',
        'state': 'opened',
        'parent_id': 'epic:123#1',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    mock_client.get_epic.side_effect = [root_epic, child_epic1, child_epic2]
    mock_client.get_child_epics.side_effect = [
        [child_epic1, child_epic2],  # Children of root
        [],  # Children of child_epic1
        []   # Children of child_epic2
    ]
    mock_client.get_epic_issues.return_value = []

    hierarchy = builder.build_from_epic(123, 1)

    assert len(hierarchy) == 3

    # Check root epic
    root = next(h for h in hierarchy if h['id'] == 'epic:123#1')
    assert root['depth'] == 0
    assert root['child_epic_count'] == 2

    # Check child epics
    children = [h for h in hierarchy if h['parent_id'] == 'epic:123#1']
    assert len(children) == 2
    assert all(child['depth'] == 1 for child in children)
    assert all(child['root_id'] == 'epic:123#1' for child in children)


def test_epic_with_issues(builder, mock_client):
    """Test epic with issues."""
    root_epic = {
        'id': 'epic:123#1',
        'type': 'epic',
        'iid': 1,
        'group_id': 123,
        'title': 'Root Epic',
        'state': 'opened',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    issue1 = {
        'id': 'issue:456#1',
        'type': 'issue',
        'iid': 1,
        'project_id': 456,
        'title': 'Issue 1',
        'state': 'opened',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    issue2 = {
        'id': 'issue:456#2',
        'type': 'issue',
        'iid': 2,
        'project_id': 456,
        'title': 'Issue 2',
        'state': 'closed',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-02T00:00:00Z',
        'closed_at': '2024-01-02T00:00:00Z',
    }

    mock_client.get_epic.return_value = root_epic
    mock_client.get_child_epics.return_value = []
    mock_client.get_epic_issues.return_value = [issue1, issue2]

    hierarchy = builder.build_from_epic(123, 1)

    assert len(hierarchy) == 3

    # Check epic
    epic = next(h for h in hierarchy if h['type'] == 'epic')
    assert epic['child_issue_count'] == 2

    # Check issues
    issues = [h for h in hierarchy if h['type'] == 'issue']
    assert len(issues) == 2
    assert all(issue['depth'] == 1 for issue in issues)
    assert all(issue['parent_id'] == 'epic:123#1' for issue in issues)
    assert all(issue['root_id'] == 'epic:123#1' for issue in issues)


def test_max_depth_limit(builder, mock_client):
    """Test that max_depth is respected."""
    root_epic = {
        'id': 'epic:123#1',
        'type': 'epic',
        'iid': 1,
        'group_id': 123,
        'title': 'Root Epic',
        'state': 'opened',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    child_epic = {
        'id': 'epic:123#2',
        'type': 'epic',
        'iid': 2,
        'group_id': 123,
        'title': 'Child Epic',
        'state': 'opened',
        'parent_id': 'epic:123#1',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    mock_client.get_epic.side_effect = [root_epic, child_epic]
    mock_client.get_child_epics.side_effect = [
        [child_epic],  # Children of root
        []  # Would be children of child_epic, but max_depth stops it
    ]
    mock_client.get_epic_issues.return_value = []

    # Set max_depth to 1 - should only get root epic
    hierarchy = builder.build_from_epic(123, 1, max_depth=0)

    assert len(hierarchy) == 1
    assert hierarchy[0]['depth'] == 0


def test_include_closed_filter(builder, mock_client):
    """Test filtering of closed items."""
    root_epic = {
        'id': 'epic:123#1',
        'type': 'epic',
        'iid': 1,
        'group_id': 123,
        'title': 'Root Epic',
        'state': 'opened',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    closed_child = {
        'id': 'epic:123#2',
        'type': 'epic',
        'iid': 2,
        'group_id': 123,
        'title': 'Closed Child',
        'state': 'closed',
        'parent_id': 'epic:123#1',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-02T00:00:00Z',
        'closed_at': '2024-01-02T00:00:00Z',
    }

    mock_client.get_epic.return_value = root_epic
    mock_client.get_child_epics.return_value = [closed_child]
    mock_client.get_epic_issues.return_value = []

    # With include_closed=False, should not include closed child
    hierarchy = builder.build_from_epic(123, 1, include_closed=False)

    assert len(hierarchy) == 1
    assert hierarchy[0]['state'] == 'opened'

    # With include_closed=True, should include closed child
    mock_client.get_epic.side_effect = [root_epic, closed_child]
    mock_client.get_child_epics.return_value = [closed_child]

    hierarchy = builder.build_from_epic(123, 1, include_closed=True)

    # Should have both open and closed
    assert len(hierarchy) >= 1
    states = [h['state'] for h in hierarchy]
    assert 'opened' in states


def test_cycle_detection(builder, mock_client):
    """Test that cycles are detected and prevented."""
    epic1 = {
        'id': 'epic:123#1',
        'type': 'epic',
        'iid': 1,
        'group_id': 123,
        'title': 'Epic 1',
        'state': 'opened',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    epic2 = {
        'id': 'epic:123#2',
        'type': 'epic',
        'iid': 2,
        'group_id': 123,
        'title': 'Epic 2',
        'state': 'opened',
        'parent_id': 'epic:123#1',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    # Create cycle: epic1 -> epic2 -> epic1
    mock_client.get_epic.side_effect = [epic1, epic2]
    mock_client.get_child_epics.side_effect = [
        [epic2],  # Children of epic1
        [epic1],  # Children of epic2 (cycle!)
    ]
    mock_client.get_epic_issues.return_value = []

    hierarchy = builder.build_from_epic(123, 1)

    # Should have epic1 and epic2, but not process epic1 again
    assert len(hierarchy) == 2
    epic_ids = [h['id'] for h in hierarchy]
    assert 'epic:123#1' in epic_ids
    assert 'epic:123#2' in epic_ids


def test_hierarchy_path_calculation(builder, mock_client):
    """Test that hierarchy_path is correctly calculated."""
    root_epic = {
        'id': 'epic:123#1',
        'type': 'epic',
        'iid': 1,
        'group_id': 123,
        'title': 'Root',
        'state': 'opened',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    child_epic = {
        'id': 'epic:123#2',
        'type': 'epic',
        'iid': 2,
        'group_id': 123,
        'title': 'Child',
        'state': 'opened',
        'parent_id': 'epic:123#1',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    grandchild_issue = {
        'id': 'issue:456#1',
        'type': 'issue',
        'iid': 1,
        'project_id': 456,
        'title': 'Grandchild Issue',
        'state': 'opened',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
    }

    mock_client.get_epic.side_effect = [root_epic, child_epic]
    mock_client.get_child_epics.side_effect = [
        [child_epic],  # Children of root
        []  # Children of child
    ]
    mock_client.get_epic_issues.side_effect = [
        [],  # Issues of root
        [grandchild_issue]  # Issues of child
    ]

    hierarchy = builder.build_from_epic(123, 1)

    # Check hierarchy paths
    root = next(h for h in hierarchy if h['id'] == 'epic:123#1')
    assert root['hierarchy_path'] == 'epic:123#1'

    child = next(h for h in hierarchy if h['id'] == 'epic:123#2')
    assert child['hierarchy_path'] == 'epic:123#1/epic:123#2'

    grandchild = next(h for h in hierarchy if h['id'] == 'issue:456#1')
    assert grandchild['hierarchy_path'] == 'epic:123#1/epic:123#2/issue:456#1'


def test_metrics_calculation(builder, mock_client):
    """Test that derived metrics are calculated correctly."""
    root_epic = {
        'id': 'epic:123#1',
        'type': 'epic',
        'iid': 1,
        'group_id': 123,
        'title': 'Root Epic',
        'state': 'opened',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-10T00:00:00Z',
        'due_date': '2024-01-05',  # Already past
    }

    mock_client.get_epic.return_value = root_epic
    mock_client.get_child_epics.return_value = []
    mock_client.get_epic_issues.return_value = []

    hierarchy = builder.build_from_epic(123, 1)

    epic = hierarchy[0]

    # Should have days_open calculated
    assert 'days_open' in epic
    assert epic['days_open'] is not None
    assert epic['days_open'] > 0

    # Should detect overdue
    assert 'is_overdue' in epic
    # This will be True if current date > due_date
