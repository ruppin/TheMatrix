"""
Database models and schema definitions for GitLab hierarchy.
"""

# Database schema for gitlab_hierarchy table
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gitlab_hierarchy (
    -- Identity & Type Fields
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    iid INTEGER NOT NULL,
    group_id INTEGER,
    project_id INTEGER,
    group_path TEXT,
    project_path TEXT,

    -- Hierarchy Fields
    parent_id TEXT,
    parent_type TEXT,
    root_id TEXT NOT NULL,
    depth INTEGER NOT NULL,
    hierarchy_path TEXT,
    is_leaf INTEGER DEFAULT 0,
    child_count INTEGER DEFAULT 0,
    descendant_count INTEGER DEFAULT 0,
    sibling_position INTEGER,

    -- Core Attributes
    title TEXT NOT NULL,
    description TEXT,
    state TEXT NOT NULL,
    web_url TEXT,
    author_username TEXT,
    author_name TEXT,
    assignee_username TEXT,
    assignee_name TEXT,
    milestone_title TEXT,
    milestone_id INTEGER,

    -- Epic-Specific Fields
    epic_state_event TEXT,
    start_date DATE,
    end_date DATE,
    parent_epic_id INTEGER,

    -- Issue-Specific Fields
    issue_type TEXT,
    confidential INTEGER DEFAULT 0,
    discussion_locked INTEGER DEFAULT 0,
    issue_link_type TEXT,
    weight INTEGER,
    time_estimate INTEGER,
    time_spent INTEGER,
    severity TEXT,
    epic_iid INTEGER,
    epic_issue_id INTEGER,

    -- Labels (Normalized)
    labels_raw TEXT,
    label_priority TEXT,
    label_type TEXT,
    label_status TEXT,
    label_team TEXT,
    label_component TEXT,
    label_custom_1 TEXT,
    label_custom_2 TEXT,
    label_custom_3 TEXT,

    -- Dates & Time Tracking
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    due_date DATE,
    last_edited_at TIMESTAMP,
    last_edited_by TEXT,

    -- Metrics & Derived Fields
    days_open INTEGER,
    days_to_close INTEGER,
    is_overdue INTEGER DEFAULT 0,
    days_overdue INTEGER,
    completion_pct REAL,
    story_points INTEGER,
    blocked_by_count INTEGER DEFAULT 0,
    blocks_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,

    -- Relationship Fields
    blocks TEXT,
    blocked_by TEXT,
    related_issues TEXT,
    related_merge_requests TEXT,

    -- Snapshot & Versioning
    snapshot_date DATE NOT NULL,
    data_version INTEGER DEFAULT 1,
    is_latest INTEGER DEFAULT 1,

    -- Additional Metadata
    has_tasks INTEGER DEFAULT 0,
    task_completion_status TEXT,
    references TEXT,
    moved_to_id INTEGER,
    duplicated_to_id INTEGER,
    closed_by TEXT,
    merged_by TEXT,
    merge_requests_count INTEGER DEFAULT 0,
    user_notes_count INTEGER DEFAULT 0
);
"""

# Indexes for performance
INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_type ON gitlab_hierarchy(type);",
    "CREATE INDEX IF NOT EXISTS idx_state ON gitlab_hierarchy(state);",
    "CREATE INDEX IF NOT EXISTS idx_root_id ON gitlab_hierarchy(root_id);",
    "CREATE INDEX IF NOT EXISTS idx_parent_id ON gitlab_hierarchy(parent_id);",
    "CREATE INDEX IF NOT EXISTS idx_depth ON gitlab_hierarchy(depth);",
    "CREATE INDEX IF NOT EXISTS idx_snapshot_date ON gitlab_hierarchy(snapshot_date);",
    "CREATE INDEX IF NOT EXISTS idx_assignee ON gitlab_hierarchy(assignee_username);",
    "CREATE INDEX IF NOT EXISTS idx_created_at ON gitlab_hierarchy(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_is_latest ON gitlab_hierarchy(is_latest);",
    "CREATE INDEX IF NOT EXISTS idx_composite_query ON gitlab_hierarchy(root_id, depth, state, is_latest);",
]


class HierarchyItem:
    """Base class for hierarchy items (epics and issues)."""

    def __init__(self, item_type, iid, **kwargs):
        self.type = item_type
        self.iid = iid
        self.data = kwargs

    def to_dict(self):
        """Convert to dictionary for database insertion."""
        return {
            'type': self.type,
            'iid': self.iid,
            **self.data
        }

    @property
    def id(self):
        """Generate unique ID for this item."""
        if self.type == 'epic':
            return f"epic:{self.data.get('group_id')}#{self.iid}"
        else:
            return f"issue:{self.data.get('project_id')}#{self.iid}"


class Epic(HierarchyItem):
    """Represents a GitLab Epic."""

    def __init__(self, iid, group_id, **kwargs):
        super().__init__('epic', iid, group_id=group_id, **kwargs)


class Issue(HierarchyItem):
    """Represents a GitLab Issue."""

    def __init__(self, iid, project_id, **kwargs):
        super().__init__('issue', iid, project_id=project_id, **kwargs)
