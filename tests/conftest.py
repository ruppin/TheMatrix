"""
Shared pytest fixtures for gitlab_hierarchy tests.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime, date


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def sample_epic_data():
    """Sample epic data for testing."""
    return {
        'id': 'epic:123#1',
        'type': 'epic',
        'iid': 1,
        'group_id': 123,
        'title': 'Test Epic',
        'description': 'A test epic for unit tests',
        'state': 'opened',
        'web_url': 'https://gitlab.example.com/groups/test/-/epics/1',
        'author_username': 'testuser',
        'author_name': 'Test User',
        'assignee_username': None,
        'assignee_name': None,
        'labels': ['priority:high', 'type:epic', 'team:backend'],
        'milestone_title': 'Q1 2024',
        'start_date': '2024-01-01',
        'end_date': '2024-03-31',
        'due_date': None,
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-15T00:00:00Z',
        'closed_at': None,
        'root_id': 'epic:123#1',
        'parent_id': None,
        'depth': 0,
        'hierarchy_path': 'epic:123#1',
        'child_epic_count': 0,
        'child_issue_count': 0,
        'descendant_count': 0,
    }


@pytest.fixture
def sample_issue_data():
    """Sample issue data for testing."""
    return {
        'id': 'issue:456#1',
        'type': 'issue',
        'iid': 1,
        'project_id': 456,
        'title': 'Test Issue',
        'description': 'A test issue for unit tests',
        'state': 'opened',
        'web_url': 'https://gitlab.example.com/project/repo/-/issues/1',
        'author_username': 'testuser',
        'author_name': 'Test User',
        'assignee_username': 'assignee',
        'assignee_name': 'Assignee User',
        'labels': ['bug', 'priority:high', 'status:in-progress'],
        'milestone_title': 'Sprint 10',
        'issue_type': 'issue',
        'weight': 3,
        'time_estimate': 7200,
        'time_spent': 3600,
        'due_date': '2024-02-01',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-15T00:00:00Z',
        'closed_at': None,
        'root_id': 'epic:123#1',
        'parent_id': 'epic:123#1',
        'depth': 1,
        'hierarchy_path': 'epic:123#1/issue:456#1',
        'blocks': [],
        'blocked_by': [],
        'blocked_by_count': 0,
        'has_tasks': True,
        'task_completion_status': {'count': 5, 'completed_count': 2},
    }


@pytest.fixture
def sample_hierarchy():
    """Sample hierarchy with epic and issues."""
    root_epic = {
        'id': 'epic:123#1',
        'type': 'epic',
        'iid': 1,
        'group_id': 123,
        'title': 'Root Epic',
        'state': 'opened',
        'root_id': 'epic:123#1',
        'parent_id': None,
        'depth': 0,
        'hierarchy_path': 'epic:123#1',
        'labels': ['priority:high'],
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z',
        'child_epic_count': 1,
        'child_issue_count': 2,
    }

    child_epic = {
        'id': 'epic:123#2',
        'type': 'epic',
        'iid': 2,
        'group_id': 123,
        'title': 'Child Epic',
        'state': 'opened',
        'root_id': 'epic:123#1',
        'parent_id': 'epic:123#1',
        'depth': 1,
        'hierarchy_path': 'epic:123#1/epic:123#2',
        'labels': ['priority:medium'],
        'created_at': '2024-01-02T00:00:00Z',
        'updated_at': '2024-01-02T00:00:00Z',
        'child_epic_count': 0,
        'child_issue_count': 1,
    }

    issue1 = {
        'id': 'issue:456#1',
        'type': 'issue',
        'iid': 1,
        'project_id': 456,
        'title': 'Issue 1',
        'state': 'opened',
        'root_id': 'epic:123#1',
        'parent_id': 'epic:123#1',
        'depth': 1,
        'hierarchy_path': 'epic:123#1/issue:456#1',
        'labels': ['bug', 'priority:high'],
        'created_at': '2024-01-03T00:00:00Z',
        'updated_at': '2024-01-03T00:00:00Z',
    }

    issue2 = {
        'id': 'issue:456#2',
        'type': 'issue',
        'iid': 2,
        'project_id': 456,
        'title': 'Issue 2',
        'state': 'closed',
        'root_id': 'epic:123#1',
        'parent_id': 'epic:123#1',
        'depth': 1,
        'hierarchy_path': 'epic:123#1/issue:456#2',
        'labels': ['feature', 'priority:low'],
        'created_at': '2024-01-04T00:00:00Z',
        'updated_at': '2024-01-05T00:00:00Z',
        'closed_at': '2024-01-05T00:00:00Z',
    }

    issue3 = {
        'id': 'issue:456#3',
        'type': 'issue',
        'iid': 3,
        'project_id': 456,
        'title': 'Issue 3',
        'state': 'opened',
        'root_id': 'epic:123#1',
        'parent_id': 'epic:123#2',
        'depth': 2,
        'hierarchy_path': 'epic:123#1/epic:123#2/issue:456#3',
        'labels': ['bug', 'priority:medium'],
        'created_at': '2024-01-06T00:00:00Z',
        'updated_at': '2024-01-06T00:00:00Z',
    }

    return [root_epic, child_epic, issue1, issue2, issue3]


@pytest.fixture
def mock_gitlab_epic():
    """Create a mock GitLab epic object."""
    epic = Mock()
    epic.iid = 1
    epic.id = 'gid://gitlab/Epic/123'
    epic.title = 'Mock Epic'
    epic.description = 'Mock description'
    epic.state = 'opened'
    epic.labels = ['priority:high', 'type:epic']
    epic.web_url = 'https://gitlab.example.com/groups/test/-/epics/1'
    epic.created_at = '2024-01-01T00:00:00Z'
    epic.updated_at = '2024-01-01T00:00:00Z'
    epic.start_date = None
    epic.end_date = None
    epic.parent_id = None
    epic.author = Mock(username='author', name='Author Name')
    epic.assignees = []
    return epic


@pytest.fixture
def mock_gitlab_issue():
    """Create a mock GitLab issue object."""
    issue = Mock()
    issue.iid = 1
    issue.id = 456
    issue.project_id = 789
    issue.title = 'Mock Issue'
    issue.description = 'Mock description'
    issue.state = 'opened'
    issue.labels = ['bug', 'priority:high']
    issue.web_url = 'https://gitlab.example.com/project/repo/-/issues/1'
    issue.created_at = '2024-01-01T00:00:00Z'
    issue.updated_at = '2024-01-01T00:00:00Z'
    issue.closed_at = None
    issue.due_date = None
    issue.weight = 3
    issue.author = Mock(username='author', name='Author Name')
    issue.assignees = []
    issue.milestone = None
    issue.time_stats = Mock(
        time_estimate=7200,
        total_time_spent=3600
    )
    issue.task_completion_status = {'count': 5, 'completed_count': 2}
    return issue


@pytest.fixture
def sample_labels():
    """Sample label sets for testing."""
    return {
        'standard': [
            'priority:high',
            'type:bug',
            'status:in-progress',
            'team:backend',
            'component:api'
        ],
        'custom': [
            'severity:critical',
            'area:authentication',
            'env:production'
        ],
        'mixed': [
            'priority:medium',
            'custom-cat:value',
            'simple-label'
        ],
        'empty': []
    }


@pytest.fixture
def sample_snapshot_date():
    """Sample snapshot date for testing."""
    return date(2024, 1, 15)


# Markers for test categorization
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "database: Database tests")
    config.addinivalue_line("markers", "api: API-related tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
