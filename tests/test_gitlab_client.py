"""
Tests for GitLab client wrapper.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from gitlab_hierarchy.gitlab_client import GitLabClient


@pytest.fixture
def mock_gitlab():
    """Create a mock GitLab instance."""
    with patch('gitlab_hierarchy.gitlab_client.gitlab.Gitlab') as mock_gl:
        instance = Mock()
        mock_gl.return_value = instance
        yield instance


@pytest.fixture
def client(mock_gitlab):
    """Create a GitLabClient with mocked gitlab library."""
    with patch.dict('os.environ', {'GITLAB_TOKEN': 'test-token'}):
        return GitLabClient(gitlab_url='https://gitlab.example.com')


def test_client_initialization(mock_gitlab):
    """Test client initialization with various auth methods."""
    # Test with token from parameter
    with patch.dict('os.environ', clear=True):
        client = GitLabClient(
            gitlab_url='https://gitlab.example.com',
            token='param-token'
        )
    mock_gitlab.assert_called_with(
        'https://gitlab.example.com',
        private_token='param-token'
    )

    # Test with token from environment
    with patch.dict('os.environ', {'GITLAB_TOKEN': 'env-token'}):
        client = GitLabClient(gitlab_url='https://gitlab.example.com')
    mock_gitlab.assert_called_with(
        'https://gitlab.example.com',
        private_token='env-token'
    )


def test_client_initialization_no_token(mock_gitlab):
    """Test that missing token raises error."""
    with patch.dict('os.environ', clear=True):
        with pytest.raises(ValueError, match='GitLab token is required'):
            GitLabClient(gitlab_url='https://gitlab.example.com')


def test_get_epic(client, mock_gitlab):
    """Test fetching a single epic."""
    mock_group = Mock()
    mock_epic = Mock()
    mock_epic.iid = 10
    mock_epic.id = 'gid://gitlab/Epic/123'
    mock_epic.title = 'Test Epic'
    mock_epic.state = 'opened'
    mock_epic.labels = ['priority:high', 'type:epic']
    mock_epic.web_url = 'https://gitlab.example.com/groups/test/-/epics/10'
    mock_epic.created_at = '2024-01-01T00:00:00Z'
    mock_epic.updated_at = '2024-01-01T00:00:00Z'
    mock_epic.start_date = None
    mock_epic.end_date = None
    mock_epic.parent_id = None

    mock_group.epics.get.return_value = mock_epic
    mock_gitlab.groups.get.return_value = mock_group

    result = client.get_epic(123, 10)

    assert result is not None
    assert result['id'] == 'epic:123#10'
    assert result['type'] == 'epic'
    assert result['title'] == 'Test Epic'
    assert result['state'] == 'opened'
    assert result['group_id'] == 123
    assert result['iid'] == 10


def test_get_child_epics(client, mock_gitlab):
    """Test fetching child epics."""
    mock_group = Mock()

    # Create mock child epics
    child1 = Mock()
    child1.iid = 11
    child1.id = 'gid://gitlab/Epic/124'
    child1.title = 'Child Epic 1'
    child1.state = 'opened'
    child1.labels = []
    child1.web_url = 'https://gitlab.example.com/groups/test/-/epics/11'
    child1.created_at = '2024-01-01T00:00:00Z'
    child1.updated_at = '2024-01-01T00:00:00Z'
    child1.start_date = None
    child1.end_date = None
    child1.parent_id = 10

    child2 = Mock()
    child2.iid = 12
    child2.id = 'gid://gitlab/Epic/125'
    child2.title = 'Child Epic 2'
    child2.state = 'opened'
    child2.labels = []
    child2.web_url = 'https://gitlab.example.com/groups/test/-/epics/12'
    child2.created_at = '2024-01-01T00:00:00Z'
    child2.updated_at = '2024-01-01T00:00:00Z'
    child2.start_date = None
    child2.end_date = None
    child2.parent_id = 10

    mock_group.epics.list.return_value = [child1, child2]
    mock_gitlab.groups.get.return_value = mock_group

    results = client.get_child_epics(123, 10)

    assert len(results) == 2
    assert results[0]['id'] == 'epic:123#11'
    assert results[1]['id'] == 'epic:123#12'
    assert all(r['type'] == 'epic' for r in results)

    # Verify that list was called with parent_id filter
    mock_group.epics.list.assert_called_once()
    call_kwargs = mock_group.epics.list.call_args[1]
    assert call_kwargs['parent_id'] == 10
    assert call_kwargs['all'] == True


def test_get_epic_issues(client, mock_gitlab):
    """Test fetching issues in an epic."""
    mock_group = Mock()
    mock_epic = Mock()

    # Create mock issues
    issue1 = Mock()
    issue1.iid = 1
    issue1.id = 456
    issue1.project_id = 789
    issue1.title = 'Issue 1'
    issue1.state = 'opened'
    issue1.labels = ['priority:high']
    issue1.web_url = 'https://gitlab.example.com/project/repo/-/issues/1'
    issue1.created_at = '2024-01-01T00:00:00Z'
    issue1.updated_at = '2024-01-01T00:00:00Z'
    issue1.closed_at = None
    issue1.due_date = None

    mock_epic.issues.list.return_value = [issue1]
    mock_group.epics.get.return_value = mock_epic
    mock_gitlab.groups.get.return_value = mock_group

    results = client.get_epic_issues(123, 10)

    assert len(results) == 1
    assert results[0]['id'] == 'issue:789#1'
    assert results[0]['type'] == 'issue'
    assert results[0]['title'] == 'Issue 1'
    assert results[0]['project_id'] == 789


def test_get_issue(client, mock_gitlab):
    """Test fetching a single issue."""
    mock_project = Mock()
    mock_issue = Mock()
    mock_issue.iid = 1
    mock_issue.id = 456
    mock_issue.title = 'Test Issue'
    mock_issue.state = 'opened'
    mock_issue.labels = ['bug', 'priority:high']
    mock_issue.web_url = 'https://gitlab.example.com/project/repo/-/issues/1'
    mock_issue.created_at = '2024-01-01T00:00:00Z'
    mock_issue.updated_at = '2024-01-01T00:00:00Z'
    mock_issue.closed_at = None
    mock_issue.due_date = None
    mock_issue.weight = 3
    mock_issue.assignees = []
    mock_issue.milestone = None

    mock_project.issues.get.return_value = mock_issue
    mock_gitlab.projects.get.return_value = mock_project

    result = client.get_issue(789, 1)

    assert result is not None
    assert result['id'] == 'issue:789#1'
    assert result['type'] == 'issue'
    assert result['title'] == 'Test Issue'
    assert result['weight'] == 3


def test_get_issue_links(client, mock_gitlab):
    """Test fetching issue relationships."""
    mock_project = Mock()
    mock_issue = Mock()

    # Mock blocking link
    blocking_link = Mock()
    blocking_link.link_type = 'blocks'
    blocking_link_issue = Mock()
    blocking_link_issue.iid = 2
    blocking_link.issue = blocking_link_issue

    # Mock blocked_by link
    blocked_link = Mock()
    blocked_link.link_type = 'is_blocked_by'
    blocked_link_issue = Mock()
    blocked_link_issue.iid = 3
    blocked_link.issue = blocked_link_issue

    mock_issue.links.list.return_value = [blocking_link, blocked_link]
    mock_project.issues.get.return_value = mock_issue
    mock_gitlab.projects.get.return_value = mock_project

    blocks, blocked_by = client.get_issue_links(789, 1)

    assert len(blocks) == 1
    assert blocks[0] == 2
    assert len(blocked_by) == 1
    assert blocked_by[0] == 3


def test_rate_limiting(client, mock_gitlab):
    """Test that rate limiting delay is applied."""
    mock_group = Mock()
    mock_epic = Mock()
    mock_epic.iid = 10
    mock_epic.id = 'gid://gitlab/Epic/123'
    mock_epic.title = 'Test Epic'
    mock_epic.state = 'opened'
    mock_epic.labels = []
    mock_epic.web_url = 'https://gitlab.example.com/groups/test/-/epics/10'
    mock_epic.created_at = '2024-01-01T00:00:00Z'
    mock_epic.updated_at = '2024-01-01T00:00:00Z'
    mock_epic.start_date = None
    mock_epic.end_date = None
    mock_epic.parent_id = None

    mock_group.epics.get.return_value = mock_epic
    mock_gitlab.groups.get.return_value = mock_group

    with patch('time.sleep') as mock_sleep:
        client.get_epic(123, 10)
        # Rate limit delay should be called
        mock_sleep.assert_called_once()


def test_error_handling(client, mock_gitlab):
    """Test error handling for API failures."""
    mock_group = Mock()
    mock_group.epics.get.side_effect = Exception('API Error')
    mock_gitlab.groups.get.return_value = mock_group

    # Should log error and return None instead of raising
    result = client.get_epic(123, 10)
    assert result is None


def test_get_group_info(client, mock_gitlab):
    """Test fetching group information."""
    mock_group = Mock()
    mock_group.id = 123
    mock_group.name = 'Test Group'
    mock_group.full_path = 'parent/test-group'
    mock_group.web_url = 'https://gitlab.example.com/groups/parent/test-group'

    mock_gitlab.groups.get.return_value = mock_group

    result = client.get_group_info(123)

    assert result is not None
    assert result['id'] == 123
    assert result['name'] == 'Test Group'
    assert result['full_path'] == 'parent/test-group'


def test_get_project_info(client, mock_gitlab):
    """Test fetching project information."""
    mock_project = Mock()
    mock_project.id = 789
    mock_project.name = 'Test Project'
    mock_project.path_with_namespace = 'parent/test-group/test-project'
    mock_project.web_url = 'https://gitlab.example.com/parent/test-group/test-project'

    mock_gitlab.projects.get.return_value = mock_project

    result = client.get_project_info(789)

    assert result is not None
    assert result['id'] == 789
    assert result['name'] == 'Test Project'
    assert result['path_with_namespace'] == 'parent/test-group/test-project'
