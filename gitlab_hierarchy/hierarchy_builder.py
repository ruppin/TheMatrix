"""
Hierarchy tree traversal and relationship building logic.
"""

import logging
from typing import Dict, List, Set, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class HierarchyBuilder:
    """Build hierarchy tree from GitLab epics and issues."""

    def __init__(self, gitlab_client):
        """
        Initialize hierarchy builder.

        Args:
            gitlab_client: GitLabClient instance
        """
        self.client = gitlab_client
        self.visited_epics: Set[str] = set()
        self.visited_issues: Set[str] = set()
        self.all_items: List[Dict] = []

    def build_from_epic(
        self,
        group_id: int,
        epic_iid: int,
        max_depth: int = 20,
        include_closed: bool = True
    ) -> List[Dict]:
        """
        Build complete hierarchy starting from a root epic.

        Args:
            group_id: Group ID of root epic
            epic_iid: IID of root epic
            max_depth: Maximum depth to traverse
            include_closed: Include closed items

        Returns:
            List of all items in hierarchy with metadata
        """
        logger.info(f"Building hierarchy from epic: group {group_id}, epic #{epic_iid}")

        # Reset state
        self.visited_epics.clear()
        self.visited_issues.clear()
        self.all_items.clear()

        # Fetch root epic
        try:
            root_epic = self.client.get_epic(group_id, epic_iid)
        except Exception as e:
            logger.error(f"Failed to fetch root epic: {e}")
            raise

        root_id = root_epic['id']
        logger.info(f"Root epic: {root_epic['title']}")

        # Add root epic at depth 0
        root_epic['depth'] = 0
        root_epic['root_id'] = root_id
        root_epic['parent_id'] = None
        root_epic['parent_type'] = None
        root_epic['hierarchy_path'] = root_id
        self.all_items.append(root_epic)
        self.visited_epics.add(root_id)

        # Recursively traverse child epics
        self._traverse_child_epics(
            group_id=group_id,
            parent_epic_id=root_epic['internal_id'],
            parent_id=root_id,
            root_id=root_id,
            depth=1,
            max_depth=max_depth,
            hierarchy_path=root_id
        )

        # Recursively traverse issues in all epics
        epic_count = 0
        for item in self.all_items:
            if item['type'] == 'epic':
                epic_count += 1
                self._traverse_epic_issues(
                    group_id=item['group_id'],
                    epic_iid=item['iid'],
                    parent_id=item['id'],
                    root_id=root_id,
                    depth=item['depth'] + 1,
                    hierarchy_path=item['hierarchy_path']
                )

        logger.info(f"✓ Found {epic_count} epics")
        logger.info(f"✓ Found {len(self.all_items) - epic_count} issues")

        # Calculate relationships and metrics
        self._calculate_relationships()
        self._calculate_metrics(include_closed)

        logger.info(f"✓ Built complete hierarchy: {len(self.all_items)} total items")

        return self.all_items

    def build_from_groups(
        self,
        group_ids: List[int],
        root_epic_iid: int,
        root_group_id: int,
        max_depth: int = 20,
        include_closed: bool = True
    ) -> List[Dict]:
        """
        Build hierarchy by fetching all epics first, then building relationships.

        This approach is more reliable when group.epics.list(parent_id=...)
        doesn't properly filter epics by parent. Instead of relying on GitLab's
        API filtering, this method fetches all epics from the specified groups
        and builds the hierarchy in-memory using parent_epic_id relationships.

        Args:
            group_ids: List of group IDs to fetch epics from
            root_epic_iid: IID of the root epic
            root_group_id: Group ID containing the root epic
            max_depth: Maximum hierarchy depth
            include_closed: Include closed items in metrics

        Returns:
            List of all items (epics and issues) with hierarchy metadata
        """
        logger.info(f"Building hierarchy from {len(group_ids)} groups using in-memory method")

        # Reset state
        self.visited_epics.clear()
        self.visited_issues.clear()
        self.all_items.clear()

        # Step 1: Fetch ALL epics from all groups upfront
        logger.info("Fetching all epics from groups...")
        all_epics = self.client.get_all_epics_for_groups(group_ids)
        logger.info(f"Fetched {len(all_epics)} total epics")

        # Step 2: Build epic lookup by internal_id for fast parent-child matching
        epics_by_id = {epic['internal_id']: epic for epic in all_epics}
        logger.debug(f"Built lookup table for {len(epics_by_id)} epics")

        # Step 3: Find root epic
        root_epic_key = f"epic:{root_group_id}#{root_epic_iid}"
        root_epic = None
        for epic in all_epics:
            if epic['id'] == root_epic_key:
                root_epic = epic
                break

        if not root_epic:
            raise ValueError(
                f"Root epic {root_epic_iid} not found in group {root_group_id}. "
                f"Ensure group {root_group_id} is in the provided group_ids list."
            )

        root_id = root_epic['id']
        logger.info(f"Root epic: {root_epic['title']}")

        # Step 4: Initialize root epic metadata
        root_epic['depth'] = 0
        root_epic['parent_id'] = None
        root_epic['parent_type'] = None
        root_epic['root_id'] = root_id
        root_epic['hierarchy_path'] = root_id

        self.all_items.append(root_epic)
        self.visited_epics.add(root_epic['internal_id'])

        # Step 5: Recursively traverse using in-memory parent_id lookup
        self._traverse_child_epics_from_memory(
            epics_by_id=epics_by_id,
            parent_internal_id=root_epic['internal_id'],
            parent_id=root_id,
            root_id=root_id,
            depth=1,
            max_depth=max_depth,
            hierarchy_path=root_id
        )

        # Step 6: Fetch issues for all epics in the hierarchy
        epic_count = 0
        logger.info("Fetching issues for all epics in hierarchy...")
        for item in self.all_items:
            if item['type'] == 'epic':
                epic_count += 1
                self._traverse_epic_issues(
                    group_id=item['group_id'],
                    epic_iid=item['iid'],
                    parent_id=item['id'],
                    root_id=root_id,
                    depth=item['depth'] + 1,
                    hierarchy_path=item['hierarchy_path']
                )

        logger.info(f"✓ Found {epic_count} epics in hierarchy")
        logger.info(f"✓ Found {len(self.all_items) - epic_count} issues")

        # Step 7: Calculate relationships and metrics
        self._calculate_relationships()
        self._calculate_metrics(include_closed)

        logger.info(f"✓ Built complete hierarchy: {len(self.all_items)} total items")

        # Report orphaned epics (epics not in the hierarchy)
        orphaned_count = len(all_epics) - epic_count
        if orphaned_count > 0:
            logger.info(f"Note: {orphaned_count} epics were not part of the root epic's hierarchy")

        return self.all_items

    def _traverse_child_epics_from_memory(
        self,
        epics_by_id: Dict[int, Dict],
        parent_internal_id: int,
        parent_id: str,
        root_id: str,
        depth: int,
        max_depth: int,
        hierarchy_path: str
    ):
        """
        Recursively traverse child epics using in-memory parent_id lookup.

        This method builds the hierarchy by filtering epics whose parent_epic_id
        matches the current parent's internal_id, rather than relying on GitLab's
        API filtering.

        Args:
            epics_by_id: Dictionary mapping internal_id to epic dict
            parent_internal_id: Parent epic's GitLab internal ID
            parent_id: Parent's project ID (e.g., "epic:123#10")
            root_id: Root epic's project ID
            depth: Current depth in hierarchy
            max_depth: Maximum depth to traverse
            hierarchy_path: Path from root (e.g., "epic:1#1/epic:1#2")
        """
        if depth > max_depth:
            logger.warning(f"Maximum depth {max_depth} reached")
            return

        # Find all epics whose parent_epic_id matches this epic's internal_id
        child_epics = [
            epic for epic in epics_by_id.values()
            if epic.get('parent_epic_id') == parent_internal_id
        ]

        logger.debug(f"Found {len(child_epics)} children for epic ID {parent_internal_id} at depth {depth}")

        for epic in child_epics:
            epic_internal_id = epic['internal_id']
            epic_id = epic['id']

            # Cycle detection - prevent infinite loops
            if epic_internal_id in self.visited_epics:
                logger.warning(
                    f"Circular reference detected for epic {epic_id} "
                    f"(parent: {parent_id}). Skipping to avoid infinite loop."
                )
                continue

            # Add hierarchy metadata
            epic['depth'] = depth
            epic['parent_id'] = parent_id
            epic['parent_type'] = 'epic'
            epic['root_id'] = root_id
            epic['hierarchy_path'] = f"{hierarchy_path}/{epic_id}"

            self.all_items.append(epic)
            self.visited_epics.add(epic_internal_id)

            # Recurse to this epic's children
            self._traverse_child_epics_from_memory(
                epics_by_id=epics_by_id,
                parent_internal_id=epic_internal_id,
                parent_id=epic_id,
                root_id=root_id,
                depth=depth + 1,
                max_depth=max_depth,
                hierarchy_path=epic['hierarchy_path']
            )

    def _traverse_child_epics(
        self,
        group_id: int,
        parent_epic_id: int,
        parent_id: str,
        root_id: str,
        depth: int,
        max_depth: int,
        hierarchy_path: str
    ):
        """Recursively traverse child epics."""
        if depth > max_depth:
            logger.warning(f"Max depth {max_depth} reached, stopping traversal")
            return

        try:
            child_epics = self.client.get_child_epics(group_id, parent_epic_id)
            logger.debug(f"Found {len(child_epics)} child epic(s) at depth {depth}")

            for epic in child_epics:
                epic_id = epic['id']

                # Check for circular reference
                if epic_id in self.visited_epics:
                    logger.warning(f"Circular reference detected: {epic_id}")
                    continue

                # Add metadata
                epic['depth'] = depth
                epic['root_id'] = root_id
                epic['parent_id'] = parent_id
                epic['parent_type'] = 'epic'
                epic['hierarchy_path'] = f"{hierarchy_path}/{epic_id}"

                self.all_items.append(epic)
                self.visited_epics.add(epic_id)

                # Recursively traverse this epic's children
                self._traverse_child_epics(
                    group_id=group_id,
                    parent_epic_id=epic['internal_id'],
                    parent_id=epic_id,
                    root_id=root_id,
                    depth=depth + 1,
                    max_depth=max_depth,
                    hierarchy_path=epic['hierarchy_path']
                )

        except Exception as e:
            logger.warning(f"Error traversing child epics: {e}")

    def _traverse_epic_issues(
        self,
        group_id: int,
        epic_iid: int,
        parent_id: str,
        root_id: str,
        depth: int,
        hierarchy_path: str
    ):
        """Get all issues in an epic."""
        try:
            issues = self.client.get_epic_issues(group_id, epic_iid)
            logger.debug(f"Found {len(issues)} issue(s) in epic #{epic_iid}")

            for issue in issues:
                issue_id = issue['id']

                # Skip if already visited
                if issue_id in self.visited_issues:
                    continue

                # Add metadata
                issue['depth'] = depth
                issue['root_id'] = root_id
                issue['parent_id'] = parent_id
                issue['parent_type'] = 'epic'
                issue['hierarchy_path'] = f"{hierarchy_path}/{issue_id}"
                issue['epic_iid'] = epic_iid

                self.all_items.append(issue)
                self.visited_issues.add(issue_id)

                # TODO: Optionally traverse issue blocking relationships
                # This would add issues that this issue blocks

        except Exception as e:
            logger.warning(f"Error fetching epic issues: {e}")

    def _calculate_relationships(self):
        """Calculate parent-child counts and identify leaf nodes."""
        logger.info("Calculating relationships...")

        # Build parent-child map
        parent_children = {}
        for item in self.all_items:
            parent_id = item.get('parent_id')
            if parent_id:
                if parent_id not in parent_children:
                    parent_children[parent_id] = []
                parent_children[parent_id].append(item['id'])

        # Update items with child counts
        for item in self.all_items:
            item_id = item['id']
            children = parent_children.get(item_id, [])

            item['child_count'] = len(children)
            item['is_leaf'] = 1 if len(children) == 0 else 0

            # Calculate descendant count recursively
            item['descendant_count'] = self._count_descendants(item_id, parent_children)

            # Calculate sibling position
            parent_id = item.get('parent_id')
            if parent_id and parent_id in parent_children:
                siblings = parent_children[parent_id]
                item['sibling_position'] = siblings.index(item_id) + 1
            else:
                item['sibling_position'] = 1

    def _count_descendants(self, item_id: str, parent_children: Dict[str, List[str]]) -> int:
        """Recursively count all descendants."""
        children = parent_children.get(item_id, [])
        if not children:
            return 0

        count = len(children)
        for child_id in children:
            count += self._count_descendants(child_id, parent_children)

        return count

    def _calculate_metrics(self, include_closed: bool):
        """Calculate derived metrics for all items."""
        logger.info("Calculating metrics...")

        now = datetime.now(timezone.utc)

        for item in self.all_items:
            # Parse dates
            created_at = self._parse_datetime(item.get('created_at'))
            closed_at = self._parse_datetime(item.get('closed_at'))
            due_date = self._parse_date(item.get('due_date'))

            # Calculate days open
            if item['state'] == 'opened' and created_at:
                item['days_open'] = (now - created_at).days
            else:
                item['days_open'] = None

            # Calculate days to close
            if closed_at and created_at:
                item['days_to_close'] = (closed_at - created_at).days
            else:
                item['days_to_close'] = None

            # Calculate overdue
            if due_date and item['state'] == 'opened':
                item['is_overdue'] = 1 if due_date < now.date() else 0
                if item['is_overdue']:
                    item['days_overdue'] = (now.date() - due_date).days
                else:
                    item['days_overdue'] = None
            else:
                item['is_overdue'] = 0
                item['days_overdue'] = None

            # Calculate completion percentage for epics with children
            if item['type'] == 'epic' and item['child_count'] > 0:
                # Count closed children
                closed_children = sum(
                    1 for child in self.all_items
                    if child.get('parent_id') == item['id'] and child['state'] == 'closed'
                )
                item['completion_pct'] = round(100.0 * closed_children / item['child_count'], 2)
            else:
                item['completion_pct'] = None

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not dt_str:
            return None
        try:
            # Handle both with and without milliseconds
            if '.' in dt_str:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except Exception:
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime.date]:
        """Parse ISO date string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str).date()
        except Exception:
            return None
