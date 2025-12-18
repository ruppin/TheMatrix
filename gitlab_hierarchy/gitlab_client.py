"""
GitLab API client wrapper for hierarchy extraction.
"""

import logging
import time
from typing import Dict, List, Optional, Set
import gitlab
from datetime import datetime

logger = logging.getLogger(__name__)


class GitLabClient:
    """Wrapper for python-gitlab with hierarchy-specific methods."""

    def __init__(
        self,
        gitlab_url: str,
        token: str,
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit_delay: float = 0.5
    ):
        """
        Initialize GitLab client.

        Args:
            gitlab_url: GitLab instance URL
            token: Personal access token
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            rate_limit_delay: Delay between requests in seconds
        """
        self.gitlab_url = gitlab_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay

        logger.info(f"Connecting to GitLab: {gitlab_url}")

        try:
            self.gl = gitlab.Gitlab(
                url=gitlab_url,
                private_token=token,
                timeout=timeout
            )
            self.gl.auth()
            logger.info("✓ GitLab authentication successful")
        except gitlab.exceptions.GitlabAuthenticationError:
            logger.error("Authentication failed")
            raise ValueError("GitLab authentication failed. Check your token.")
        except Exception as e:
            logger.error(f"Failed to connect to GitLab: {e}")
            raise

    def get_epic(self, group_id: int, epic_iid: int) -> Dict:
        """
        Fetch a single epic by group ID and IID.

        Args:
            group_id: Group ID
            epic_iid: Epic IID

        Returns:
            Epic data dictionary
        """
        logger.debug(f"Fetching epic: group {group_id}, epic #{epic_iid}")

        try:
            group = self.gl.groups.get(group_id)
            epic = group.epics.get(epic_iid)

            return self._epic_to_dict(epic, group_id)

        except gitlab.exceptions.GitlabGetError as e:
            logger.error(f"Epic not found: group {group_id}, epic #{epic_iid}")
            raise ValueError(f"Epic {epic_iid} not found in group {group_id}") from e
        except AttributeError:
            logger.error("Epics not available (requires GitLab Premium/Ultimate)")
            raise ValueError("Epics are only available in GitLab Premium/Ultimate")

    def get_child_epics(self, group_id: int, parent_epic_id: int) -> List[Dict]:
        """
        Get all child epics of a parent epic.

        NOTE: This method relies on GitLab's parent_id filter, which may not work
        correctly in some GitLab versions. Consider using get_all_group_epics()
        and filtering in-memory instead.

        Args:
            group_id: Group ID
            parent_epic_id: Parent epic's internal ID (not IID)

        Returns:
            List of child epic dictionaries
        """
        logger.debug(f"Fetching child epics for epic ID {parent_epic_id}")

        try:
            group = self.gl.groups.get(group_id)
            # Query epics with parent_id filter
            child_epics = group.epics.list(parent_id=parent_epic_id, get_all=True)

            time.sleep(self.rate_limit_delay)

            return [self._epic_to_dict(epic, group_id) for epic in child_epics]

        except Exception as e:
            logger.warning(f"Could not fetch child epics: {e}")
            return []

    def get_all_group_epics(self, group_id: int) -> List[Dict]:
        """
        Get ALL epics in a group without filtering.

        This method fetches all epics from a group regardless of parent relationships,
        which is more reliable than using parent_id filters. The parent-child
        relationships can be built in-memory using the parent_epic_id field.

        Args:
            group_id: Group ID

        Returns:
            List of all epic dictionaries in the group
        """
        logger.debug(f"Fetching all epics for group {group_id}")

        try:
            group = self.gl.groups.get(group_id)
            # Fetch all epics WITHOUT parent_id filter
            all_epics = group.epics.list(get_all=True)

            time.sleep(self.rate_limit_delay)

            epics = [self._epic_to_dict(epic, group_id) for epic in all_epics]
            logger.info(f"Fetched {len(epics)} epics from group {group_id}")

            return epics

        except Exception as e:
            logger.warning(f"Could not fetch group epics: {e}")
            return []

    def get_all_epics_for_groups(self, group_ids: List[int]) -> List[Dict]:
        """
        Get ALL epics across multiple groups.

        This is the recommended method for building epic hierarchies that span
        multiple groups, as it's more reliable than using parent_id filters.

        Args:
            group_ids: List of group IDs

        Returns:
            List of all epic dictionaries across all groups
        """
        all_epics = []

        logger.info(f"Fetching epics from {len(group_ids)} groups")

        for group_id in group_ids:
            epics = self.get_all_group_epics(group_id)
            all_epics.extend(epics)

        logger.info(f"Fetched total of {len(all_epics)} epics from all groups")
        return all_epics

    def get_epic_issues(self, group_id: int, epic_iid: int) -> List[Dict]:
        """
        Get all issues in an epic.

        Args:
            group_id: Group ID
            epic_iid: Epic IID

        Returns:
            List of issue dictionaries
        """
        logger.debug(f"Fetching issues for epic #{epic_iid}")

        try:
            group = self.gl.groups.get(group_id)
            epic = group.epics.get(epic_iid)
            issues = epic.issues.list(get_all=True)

            time.sleep(self.rate_limit_delay)

            return [self._issue_to_dict(issue) for issue in issues]

        except Exception as e:
            logger.warning(f"Could not fetch epic issues: {e}")
            return []

    def get_issue(self, project_id: int, issue_iid: int) -> Optional[Dict]:
        """
        Fetch a single issue by project ID and IID.

        Args:
            project_id: Project ID
            issue_iid: Issue IID

        Returns:
            Issue data dictionary or None
        """
        logger.debug(f"Fetching issue: project {project_id}, issue #{issue_iid}")

        try:
            project = self.gl.projects.get(project_id)
            issue = project.issues.get(issue_iid)

            time.sleep(self.rate_limit_delay)

            return self._issue_to_dict(issue)

        except Exception as e:
            logger.warning(f"Could not fetch issue {project_id}#{issue_iid}: {e}")
            return None

    def get_issue_links(self, project_id: int, issue_iid: int) -> Dict[str, List[str]]:
        """
        Get all issue links (blocks, blocked_by, related).

        Args:
            project_id: Project ID
            issue_iid: Issue IID

        Returns:
            Dictionary with 'blocks', 'blocked_by', 'related' lists
        """
        logger.debug(f"Fetching links for issue {project_id}#{issue_iid}")

        links = {
            'blocks': [],
            'blocked_by': [],
            'related': []
        }

        try:
            project = self.gl.projects.get(project_id)
            issue = project.issues.get(issue_iid)
            issue_links = issue.links.list(get_all=True)

            for link in issue_links:
                try:
                    # Extract reference from link
                    ref = link.references.get('full', '')
                    if ref:
                        # Determine link type
                        link_type = getattr(link, 'link_type', 'relates_to')

                        if link_type == 'blocks':
                            links['blocks'].append(ref)
                        elif link_type == 'is_blocked_by':
                            links['blocked_by'].append(ref)
                        else:
                            links['related'].append(ref)
                except Exception as e:
                    logger.debug(f"Could not parse link: {e}")

            time.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.warning(f"Could not fetch issue links: {e}")

        return links

    def get_group_info(self, group_id: int) -> Dict:
        """
        Get group information.

        Args:
            group_id: Group ID

        Returns:
            Group info dictionary
        """
        try:
            group = self.gl.groups.get(group_id)
            return {
                'id': group.id,
                'name': group.name,
                'path': group.path,
                'full_path': group.full_path,
                'web_url': group.web_url
            }
        except Exception as e:
            logger.warning(f"Could not fetch group {group_id}: {e}")
            return {}

    def get_project_info(self, project_id: int) -> Dict:
        """
        Get project information.

        Args:
            project_id: Project ID

        Returns:
            Project info dictionary
        """
        try:
            project = self.gl.projects.get(project_id)
            return {
                'id': project.id,
                'name': project.name,
                'path': project.path,
                'path_with_namespace': project.path_with_namespace,
                'web_url': project.web_url
            }
        except Exception as e:
            logger.warning(f"Could not fetch project {project_id}: {e}")
            return {}

    def _epic_to_dict(self, epic, group_id: int) -> Dict:
        """Convert GitLab epic object to dictionary."""
        return {
            'type': 'epic',
            'id': f"epic:{group_id}#{epic.iid}",
            'iid': epic.iid,
            'group_id': group_id,
            'internal_id': epic.id,  # GitLab's internal ID
            'title': epic.title,
            'description': getattr(epic, 'description', ''),
            'state': epic.state,
            'web_url': epic.web_url,
            'author_username': getattr(epic.author, 'username', None) if hasattr(epic, 'author') else None,
            'author_name': getattr(epic.author, 'name', None) if hasattr(epic, 'author') else None,
            'start_date': getattr(epic, 'start_date', None),
            'end_date': getattr(epic, 'end_date', None),
            'parent_epic_id': getattr(epic, 'parent_id', None),
            'created_at': epic.created_at,
            'updated_at': epic.updated_at,
            'closed_at': getattr(epic, 'closed_at', None),
            'labels_raw': getattr(epic, 'labels', []),
            'upvotes': getattr(epic, 'upvotes', 0),
            'downvotes': getattr(epic, 'downvotes', 0),
        }

    def _issue_to_dict(self, issue) -> Dict:
        """Convert GitLab issue object to dictionary."""
        return {
            'type': 'issue',
            'id': f"issue:{issue.project_id}#{issue.iid}",
            'iid': issue.iid,
            'project_id': issue.project_id,
            'internal_id': issue.id,
            'title': issue.title,
            'description': getattr(issue, 'description', ''),
            'state': issue.state,
            'web_url': issue.web_url,
            'author_username': getattr(issue.author, 'username', None) if hasattr(issue, 'author') else None,
            'author_name': getattr(issue.author, 'name', None) if hasattr(issue, 'author') else None,
            'assignee_username': getattr(issue, 'assignee', {}).get('username') if hasattr(issue, 'assignee') and issue.assignee else None,
            'assignee_name': getattr(issue, 'assignee', {}).get('name') if hasattr(issue, 'assignee') and issue.assignee else None,
            'milestone_title': getattr(issue.milestone, 'title', None) if hasattr(issue, 'milestone') and issue.milestone else None,
            'milestone_id': getattr(issue.milestone, 'id', None) if hasattr(issue, 'milestone') and issue.milestone else None,
            'issue_type': getattr(issue, 'issue_type', 'issue'),
            'confidential': getattr(issue, 'confidential', False),
            'discussion_locked': getattr(issue, 'discussion_locked', False),
            'weight': getattr(issue, 'weight', None),
            'story_points': getattr(issue, 'weight', None),  # Alias
            'time_estimate': getattr(issue, 'time_stats', {}).get('time_estimate', 0) if hasattr(issue, 'time_stats') else 0,
            'time_spent': getattr(issue, 'time_stats', {}).get('total_time_spent', 0) if hasattr(issue, 'time_stats') else 0,
            'severity': getattr(issue, 'severity', None),
            'created_at': issue.created_at,
            'updated_at': issue.updated_at,
            'closed_at': getattr(issue, 'closed_at', None),
            'due_date': getattr(issue, 'due_date', None),
            'labels_raw': getattr(issue, 'labels', []),
            'upvotes': getattr(issue, 'upvotes', 0),
            'downvotes': getattr(issue, 'downvotes', 0),
            'user_notes_count': getattr(issue, 'user_notes_count', 0),
            'merge_requests_count': getattr(issue, 'merge_requests_count', 0),
            'has_tasks': getattr(issue, 'has_tasks', False),
            'task_completion_status': getattr(issue, 'task_completion_status', {}).get('completed_count', 0) if hasattr(issue, 'task_completion_status') else None,
        }
