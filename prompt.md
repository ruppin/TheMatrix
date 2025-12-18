# Prompt: GitLab Epic & Issue Hierarchy Extractor to SQLite

## Objective
Create a production-ready Python tool that traverses GitLab epic hierarchies starting from a root epic, captures all child epics and their issues recursively down to leaf-level issues, and stores comprehensive data in a SQLite database optimized for reporting and analytics.

## Requirements

### 1. Functional Requirements

**Core Functionality:**
- Accept a root epic (group_id, epic_iid) as starting point
- Recursively traverse the entire hierarchy:
  - Root Epic → Child Epics → Grandchild Epics → ... → Issues at all levels
- Handle cross-project issue assignments (epic in Group A containing issues from Group B)
- Handle circular references gracefully (prevent infinite loops)
- Support incremental updates (refresh existing data without full rebuild)
- Provide progress tracking for long-running traversals

**Data Capture Requirements:**
- Capture ALL available epic attributes from GitLab API
- Capture ALL available issue attributes from GitLab API
- Extract and normalize labels into separate columns
- Calculate and store derived metrics (depth, completion %, days open, etc.)
- Store relationship data (parent-child, blocking relationships)
- Track snapshot dates for historical trending

### 2. Technical Requirements

**Technology Stack:**
- Python 3.8+
- `python-gitlab` library for GitLab API
- `sqlite3` for database
- `pandas` for data manipulation
- `click` or `argparse` for CLI
- `tqdm` for progress bars
- `python-dotenv` for configuration

**Database Design:**
- Single unified table: `gitlab_hierarchy`
- Proper indexing for query performance
- Support for historical snapshots
- Normalized label columns (auto-detect from data)

**Error Handling:**
- Graceful handling of API rate limits (with retry logic)
- Handle missing permissions (log and continue)
- Handle deleted/archived items
- Detailed error logging

**Performance:**
- Batch API requests where possible
- Cache intermediate results
- Support resume from interruption
- Optimize for 1000+ items

## 3. Data Model Specification

### Table: `gitlab_hierarchy`

**Identity & Type Fields:**
id TEXT PRIMARY KEY -- Format: "epic:123#10" or "issue:456#20" type TEXT NOT NULL -- 'epic' or 'issue' iid INTEGER NOT NULL -- Internal ID within group/project group_id INTEGER -- For epics (NULL for issues) project_id INTEGER -- For issues (NULL for group epics) group_path TEXT -- Full path like "company/team/subteam" project_path TEXT -- Full path like "company/team/project"


**Hierarchy Fields:**
parent_id TEXT -- References another row's id parent_type TEXT -- 'epic' or 'issue' root_id TEXT NOT NULL -- Always points to top-most epic depth INTEGER NOT NULL -- 0=root, 1=child, 2=grandchild, etc. hierarchy_path TEXT -- Full path: "epic:123#1/epic:123#5/issue:456#20" is_leaf BOOLEAN -- TRUE if has no children child_count INTEGER -- Direct children count descendant_count INTEGER -- Total descendants count sibling_position INTEGER -- Position among siblings (1, 2, 3...)


**Core Attributes:**
title TEXT NOT NULL description TEXT state TEXT NOT NULL -- 'opened' or 'closed' web_url TEXT author_username TEXT author_name TEXT assignee_username TEXT assignee_name TEXT milestone_title TEXT milestone_id INTEGER


**Epic-Specific Fields:**
epic_state_event TEXT -- 'close', 'reopen' start_date DATE end_date DATE parent_epic_id INTEGER -- GitLab's parent_id field


**Issue-Specific Fields:**
issue_type TEXT -- 'issue', 'incident', 'test_case' confidential BOOLEAN discussion_locked BOOLEAN issue_link_type TEXT -- If linked to epic weight INTEGER -- Issue weight/story points time_estimate INTEGER -- In seconds time_spent INTEGER -- In seconds severity TEXT epic_iid INTEGER -- Epic this issue belongs to epic_issue_id INTEGER -- Epic-issue relationship ID


**Labels (Normalized):**
labels_raw TEXT -- JSON array of all labels label_priority TEXT -- Extracted: priority:high, priority:low, etc. label_type TEXT -- Extracted: type:bug, type:feature, etc. label_status TEXT -- Extracted: status:blocked, status:review, etc. label_team TEXT -- Extracted: team:frontend, team:backend, etc. label_component TEXT -- Extracted: component:api, component:ui, etc. label_custom_1 TEXT -- Auto-detected custom label category label_custom_2 TEXT -- Auto-detected custom label category label_custom_3 TEXT -- Auto-detected custom label category -- Add more label columns as needed


**Dates & Time Tracking:**
created_at TIMESTAMP NOT NULL updated_at TIMESTAMP NOT NULL closed_at TIMESTAMP due_date DATE start_date DATE -- For epics end_date DATE -- For epics last_edited_at TIMESTAMP last_edited_by TEXT


**Metrics & Derived Fields:**
days_open INTEGER -- Current age if open days_to_close INTEGER -- Time to close if closed is_overdue BOOLEAN -- due_date < today AND state='opened' days_overdue INTEGER -- How many days past due completion_pct DECIMAL -- For epics with children story_points INTEGER -- Alias for weight blocked_by_count INTEGER -- How many issues block this blocks_count INTEGER -- How many issues this blocks comment_count INTEGER -- Number of comments/notes upvotes INTEGER downvotes INTEGER


**Relationship Fields:**
blocks TEXT -- JSON array of issue IDs this blocks blocked_by TEXT -- JSON array of issue IDs blocking this related_issues TEXT -- JSON array of related issue IDs related_merge_requests TEXT -- JSON array of MR IDs


**Snapshot & Versioning:**
snapshot_date DATE NOT NULL -- When this record was captured data_version INTEGER -- Increments on each refresh is_latest BOOLEAN -- TRUE for most recent snapshot


**Additional Metadata:**
has_tasks BOOLEAN -- Description contains task list task_completion_status TEXT -- "3/5" format references TEXT -- Other items mentioned in description moved_to_id INTEGER -- If issue was moved duplicated_to_id INTEGER -- If marked as duplicate closed_by TEXT -- Who closed it merged_by TEXT -- For issues closed via MR merge_requests_count INTEGER user_notes_count INTEGER


### Indexes for Performance:
```sql
CREATE INDEX idx_type ON gitlab_hierarchy(type);
CREATE INDEX idx_state ON gitlab_hierarchy(state);
CREATE INDEX idx_root_id ON gitlab_hierarchy(root_id);
CREATE INDEX idx_parent_id ON gitlab_hierarchy(parent_id);
CREATE INDEX idx_depth ON gitlab_hierarchy(depth);
CREATE INDEX idx_snapshot_date ON gitlab_hierarchy(snapshot_date);
CREATE INDEX idx_assignee ON gitlab_hierarchy(assignee_username);
CREATE INDEX idx_created_at ON gitlab_hierarchy(created_at);
CREATE INDEX idx_is_latest ON gitlab_hierarchy(is_latest);
CREATE INDEX idx_composite_query ON gitlab_hierarchy(root_id, depth, state, is_latest);
4. CLI Interface

# Basic usage - traverse from root epic
python gitlab_hierarchy.py extract \
  --group-id 123 \
  --epic-iid 10 \
  --db hierarchy.db

# With all options
python gitlab_hierarchy.py extract \
  --group-id 123 \
  --epic-iid 10 \
  --db hierarchy.db \
  --gitlab-url https://gitlab.company.com \
  --token $GITLAB_TOKEN \
  --snapshot-date 2024-01-15 \
  --include-closed \
  --max-depth 10 \
  --batch-size 50 \
  --verbose

# Refresh existing data (incremental update)
python gitlab_hierarchy.py refresh \
  --db hierarchy.db \
  --root-id "epic:123#10"

# Extract multiple root epics
python gitlab_hierarchy.py extract-batch \
  --config epics_config.yaml \
  --db hierarchy.db

# Export to CSV for external reporting
python gitlab_hierarchy.py export \
  --db hierarchy.db \
  --format csv \
  --output reports/

# Show statistics
python gitlab_hierarchy.py stats \
  --db hierarchy.db \
  --root-id "epic:123#10"

# Clean old snapshots
python gitlab_hierarchy.py cleanup \
  --db hierarchy.db \
  --keep-days 90
5. Configuration File Format
epics_config.yaml:

gitlab:
  url: "https://gitlab.com"
  token: "${GITLAB_TOKEN}"
  timeout: 30
  max_retries: 3

database:
  path: "hierarchy.db"
  backup: true
  backup_dir: "backups/"

extraction:
  # Root epics to extract
  roots:
    - group_id: 123
      epic_iid: 10
      name: "Product Roadmap Q1"
    
    - group_id: 123
      epic_iid: 15
      name: "Infrastructure Initiative"
  
  # Options
  include_closed: true
  max_depth: 20
  batch_size: 50
  rate_limit_delay: 0.5  # seconds between requests

labels:
  # Auto-detect label patterns and create columns
  patterns:
    - prefix: "priority"
      column: "label_priority"
    - prefix: "type"
      column: "label_type"
    - prefix: "status"
      column: "label_status"
    - prefix: "team"
      column: "label_team"
    - prefix: "component"
      column: "label_component"

snapshot:
  enabled: true
  retention_days: 90
  
logging:
  level: "INFO"
  file: "gitlab_hierarchy.log"
  format: "detailed"
6. Code Structure

gitlab_hierarchy/
├── __init__.py
├── cli.py                    # CLI commands using click/argparse
├── extractor.py              # Main extraction logic
├── models.py                 # Data models and schema
├── database.py               # SQLite operations
├── gitlab_client.py          # GitLab API wrapper
├── label_parser.py           # Label normalization logic
├── metrics_calculator.py     # Derived metrics computation
├── hierarchy_builder.py      # Tree traversal and relationship logic
├── config.py                 # Configuration management
└── utils.py                  # Helper functions

tests/
├── test_extractor.py
├── test_database.py
├── test_label_parser.py
└── fixtures/                 # Mock GitLab responses
7. Key Features to Implement
Feature 1: Smart Label Parsing

# Auto-detect label patterns and create columns
labels = ["priority:high", "type:bug", "team:backend", "Q1-2024"]

# Should produce:
{
    "label_priority": "high",
    "label_type": "bug", 
    "label_team": "backend",
    "labels_raw": '["priority:high", "type:bug", "team:backend", "Q1-2024"]'
}
Feature 2: Incremental Updates

# Only fetch items modified since last snapshot
last_updated = get_last_snapshot_date(db)
new_items = fetch_modified_since(last_updated)
update_database(new_items)
Feature 3: Progress Tracking

with tqdm(total=estimated_items, desc="Extracting hierarchy") as pbar:
    for item in traverse_hierarchy(root_epic):
        process_item(item)
        pbar.update(1)
Feature 4: Relationship Tracking

# Track all relationships
def extract_relationships(issue):
    return {
        'blocks': [link.id for link in issue.links if link.type == 'blocks'],
        'blocked_by': [link.id for link in issue.links if link.type == 'is_blocked_by'],
        'related': [link.id for link in issue.links if link.type == 'relates_to']
    }
Feature 5: Historical Snapshots

# Keep historical data for trending
def insert_snapshot(item, snapshot_date):
    # Mark previous snapshots as not latest
    db.execute("""
        UPDATE gitlab_hierarchy 
        SET is_latest = FALSE 
        WHERE id = ? AND is_latest = TRUE
    """, (item.id,))
    
    # Insert new snapshot
    item['snapshot_date'] = snapshot_date
    item['is_latest'] = True
    db.insert(item)
8. Advanced Requirements
Handle Edge Cases:
Circular References: Epic A → Epic B → Epic A
Solution: Track visited nodes, skip if already visited
Cross-Group Issues: Epic in Group A contains issue from Group B
Solution: Fetch issues regardless of group/project
Moved/Archived Items: Items that no longer exist
Solution: Log warning, mark as archived in DB
Large Hierarchies: >5000 items
Solution: Batch processing, resume capability
API Rate Limits: GitLab rate limiting (default: 600 req/min)
Solution: Exponential backoff, configurable delays
Deleted Parent: Child exists but parent was deleted
Solution: Mark as orphaned, create placeholder parent
Optimization Strategies:
Batch API Calls: Fetch multiple items in single request where possible
Parallel Processing: Use threading for independent API calls
Caching: Cache group/project metadata to avoid repeated calls
Smart Refresh: Only fetch items modified since last run
Lazy Loading: Only fetch detailed data when needed
9. Sample Queries to Support
The database should efficiently support these queries:

-- 1. Epic completion status
SELECT 
    title,
    completion_pct,
    child_count,
    descendant_count
FROM gitlab_hierarchy
WHERE type = 'epic' AND is_latest = TRUE
ORDER BY completion_pct ASC;

-- 2. Overdue items by assignee
SELECT 
    assignee_username,
    COUNT(*) as overdue_count,
    SUM(story_points) as overdue_points
FROM gitlab_hierarchy
WHERE is_overdue = TRUE AND state = 'opened' AND is_latest = TRUE
GROUP BY assignee_username;

-- 3. Bottleneck detection
SELECT 
    id,
    title,
    blocks_count,
    days_open,
    state
FROM gitlab_hierarchy
WHERE blocks_count > 0 AND state = 'opened' AND is_latest = TRUE
ORDER BY blocks_count DESC, days_open DESC;

-- 4. Team workload by labels
SELECT 
    label_team,
    COUNT(*) as items,
    SUM(story_points) as total_points,
    AVG(days_open) as avg_age
FROM gitlab_hierarchy
WHERE state = 'opened' AND type = 'issue' AND is_latest = TRUE
GROUP BY label_team;

-- 5. Hierarchy health
SELECT 
    root_id,
    MAX(depth) as max_depth,
    COUNT(*) as total_items,
    AVG(depth) as avg_depth,
    COUNT(*) FILTER (WHERE is_leaf) as leaf_count
FROM gitlab_hierarchy
WHERE is_latest = TRUE
GROUP BY root_id;

-- 6. Velocity trending (requires snapshots)
SELECT 
    snapshot_date,
    COUNT(*) FILTER (WHERE state = 'closed') as completed,
    SUM(story_points) FILTER (WHERE state = 'closed') as points_completed
FROM gitlab_hierarchy
WHERE root_id = 'epic:123#10'
GROUP BY snapshot_date
ORDER BY snapshot_date;
10. Output Expectations
Console Output:

GitLab Hierarchy Extractor v1.0
================================

Configuration:
  GitLab URL: https://gitlab.com
  Root Epic: Group 123, Epic #10
  Database: hierarchy.db
  Snapshot Date: 2024-01-15

Starting extraction...

Phase 1: Discovering hierarchy structure
  ✓ Fetched root epic: "Product Roadmap Q1 2024"
  ✓ Found 5 child epics
  ✓ Found 3 grandchild epics
  → Total epics discovered: 9

Phase 2: Fetching issues
  Extracting issues: 100%|████████████| 247/247 [02:15<00:00,  1.82it/s]
  ✓ Fetched 247 issues across 12 projects

Phase 3: Building relationships
  ✓ Calculated hierarchy depths (max depth: 4)
  ✓ Identified 23 blocking relationships
  ✓ Found 189 leaf nodes

Phase 4: Parsing labels
  ✓ Detected 5 label categories
  ✓ Created columns: label_priority, label_type, label_team, label_status, label_component

Phase 5: Calculating metrics
  ✓ Computed completion percentages
  ✓ Calculated days open/overdue
  ✓ Counted descendants

Phase 6: Storing to database
  ✓ Inserted 256 total items (9 epics, 247 issues)
  ✓ Created indexes
  ✓ Marked snapshot date: 2024-01-15

Summary:
  Total Items: 256
  Epics: 9
  Issues: 247
  Open: 198 (77.3%)
  Closed: 58 (22.7%)
  Max Depth: 4 levels
  Average Depth: 2.3 levels
  
Database: hierarchy.db (2.4 MB)
Execution Time: 2m 34s

✓ Extraction complete!
Database Validation:

-- Verify data integrity
SELECT COUNT(*) as total_rows FROM gitlab_hierarchy;
SELECT type, COUNT(*) FROM gitlab_hierarchy GROUP BY type;
SELECT state, COUNT(*) FROM gitlab_hierarchy GROUP BY state;
SELECT depth, COUNT(*) FROM gitlab_hierarchy GROUP BY depth ORDER BY depth;
Log File:

2024-01-15 10:30:00 INFO Starting extraction for epic:123#10
2024-01-15 10:30:01 INFO Fetching root epic from group 123
2024-01-15 10:30:02 INFO Root epic found: "Product Roadmap Q1 2024"
2024-01-15 10:30:03 INFO Traversing child epics (level 1)
2024-01-15 10:30:05 INFO Found 5 child epics
2024-01-15 10:30:10 INFO Fetching issues for epic 123#10
2024-01-15 10:31:45 INFO Processed 247 issues
2024-01-15 10:32:00 INFO Building hierarchy relationships
2024-01-15 10:32:10 WARNING Issue 456#789 references deleted parent
2024-01-15 10:32:34 INFO Database populated successfully
2024-01-15 10:32:34 INFO Extraction completed in 2m 34s
11. Testing Requirements
Provide unit tests for:
Epic traversal with circular reference detection
Label parsing for various label formats
Database schema creation and migration
Relationship calculation
Metric computation
Incremental update logic
Error handling and retry logic
12. Documentation Requirements
Include:
README with installation and usage instructions
Architecture diagram showing data flow
Database schema documentation with ERD
Example queries for common use cases
Troubleshooting guide
API rate limit handling documentation
Sample configuration files
13. Bonus Features (Nice to Have)
Export to Excel with formatting (color-coded by state, conditional formatting)
Web dashboard (Flask/Dash) for visual exploration
Scheduled extractions (cron job support)
Email reports with summary statistics
Integration with Jira for cross-tool reporting
ML predictions (estimated completion date based on velocity)
Gantt chart generation from hierarchy data
Webhook listener for real-time updates
Multi-root support (extract multiple epic hierarchies in one run)
Custom metric plugins (user-defined calculations)
Deliverables
✅ Fully functional Python CLI tool
✅ SQLite database with complete schema
✅ Comprehensive test suite (>80% coverage)
✅ User documentation (README, usage guide)
✅ Example configuration files
✅ Sample queries document
✅ Installation script (requirements.txt, setup.py)
✅ Error handling and logging throughout
✅ Performance benchmarks documentation
✅ Migration guide for schema updates
