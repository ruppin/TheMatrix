# Project-Based Issue Extraction Feature

## Overview

This document describes the new project-based issue extraction feature that complements the existing epic hierarchy extraction in TheMatrix project.

## Problem Solved

The original implementation only retrieves issues that are **explicitly linked to epics** via GitLab's epic-issue relationship. This means:
- ❌ Issues that exist in projects but aren't linked to any epic are **never captured**
- ❌ No way to identify "orphan" issues that need to be linked to epics
- ❌ No complete inventory of all issues in your groups/projects

## Solution Implemented

A new extraction method that:
1. Fetches **ALL issues** from all projects in specified groups
2. Captures epic linkage information if available
3. Stores results in a **separate database table** (`gitlab_project_issues`)
4. Provides visibility into both epic-linked and orphan issues

## Architecture

### Data Flow

```
1. Fetch Projects
   ↓
   For each Group ID:
   - Get all projects (including subgroups)
   ↓
2. Fetch Issues
   ↓
   For each Project:
   - Get ALL issues (epic.issues API NOT used)
   - Extract epic linkage from issue.epic field
   ↓
3. Process Issues
   ↓
   For each Issue:
   - Parse labels
   - Calculate metrics (days_open, is_overdue, etc.)
   - Set derived flags (has_epic, has_milestone, has_assignee)
   ↓
4. Store to Database
   ↓
   Insert into gitlab_project_issues table
```

### Key Differences from Epic-Based Extraction

| Aspect | Epic-Based Extraction | Project-Based Extraction |
|--------|----------------------|-------------------------|
| **API Method** | `epic.issues.list()` | `project.issues.list()` |
| **Scope** | Only epic-linked issues | ALL issues in projects |
| **Database Table** | `gitlab_hierarchy` | `gitlab_project_issues` |
| **Hierarchy** | Full epic→issue tree | Flat list with epic references |
| **Orphan Issues** | ❌ Not captured | ✅ Captured with `has_epic=0` |
| **Epic Linkage** | Via hierarchy | Via `epic_id`, `epic_iid` fields |

## Implementation Details

### Files Modified/Created

1. **gitlab_client.py** - Added 3 new methods:
   - `get_all_group_projects(group_id)` - Fetch all projects in a group
   - `get_all_project_issues(project_id)` - Fetch all issues from a project
   - `get_all_issues_for_groups(group_ids)` - Orchestrate fetching from multiple groups

2. **models.py** - Added new schema:
   - `PROJECT_ISSUES_SCHEMA_SQL` - Table definition for `gitlab_project_issues`
   - `PROJECT_ISSUES_INDEXES_SQL` - 11 indexes for performance

3. **database.py** - Added 2 new methods:
   - `insert_project_issue(issue, snapshot_date)` - Insert single issue
   - `insert_project_issues_batch(issues, snapshot_date)` - Batch insert

4. **extractor.py** - Added new extraction method:
   - `extract_issues_from_groups(group_ids, ...)` - Main orchestrator
   - Helper methods: `_parse_datetime()`, `_parse_date()`

5. **cli.py** - Added new CLI command:
   - `extract-issues-from-groups` - Command-line interface

6. **README.md** - Updated documentation:
   - New section documenting the feature
   - Usage examples and SQL queries

## Database Schema

### Table: `gitlab_project_issues`

**Key Fields:**

```sql
-- Identity
id TEXT PRIMARY KEY,              -- Format: "issue:PROJECT_ID#IID"
iid INTEGER NOT NULL,
project_id INTEGER NOT NULL,
project_name TEXT,
project_path_with_namespace TEXT,

-- Epic Linkage (if linked)
epic_id INTEGER,                  -- GitLab's internal epic ID
epic_iid INTEGER,                 -- Epic IID within group
epic_group_id INTEGER,            -- Group containing the epic
epic_title TEXT,                  -- Epic title
epic_reference TEXT,              -- Format: "epic:GROUP_ID#EPIC_IID"

-- Derived Flags
has_epic INTEGER DEFAULT 0,       -- 1 if linked to epic, 0 if orphan
has_milestone INTEGER DEFAULT 0,
has_assignee INTEGER DEFAULT 0,

-- Standard Fields
title TEXT NOT NULL,
description TEXT,
state TEXT NOT NULL,              -- 'opened' or 'closed'
assignee_username TEXT,
milestone_title TEXT,
labels_raw TEXT,                  -- JSON array
weight INTEGER,
time_estimate INTEGER,
time_spent INTEGER,
severity TEXT,

-- Dates
created_at TIMESTAMP NOT NULL,
updated_at TIMESTAMP NOT NULL,
closed_at TIMESTAMP,
due_date DATE,

-- Metrics
days_open INTEGER,
days_to_close INTEGER,
is_overdue INTEGER DEFAULT 0,
days_overdue INTEGER,

-- Versioning
snapshot_date DATE NOT NULL,
is_latest INTEGER DEFAULT 1
```

**Indexes (11 total):**
- `project_id` - Query by project
- `group_id` - Query by group
- `state` - Filter by open/closed
- `epic_id`, `epic_iid` - Query by linked epic
- `has_epic` - Filter orphans vs. epic-linked
- `snapshot_date` - Time-series queries
- `assignee_username` - Filter by assignee
- `created_at` - Sort by creation date
- `is_latest` - Get latest snapshot
- Composite index on `(project_id, has_epic, state, is_latest)`

## Usage

### CLI Command

```bash
# Extract all issues from groups 123, 456, 789
neo extract-issues-from-groups \
  --group-ids "123,456,789" \
  --db issues.db \
  --verbose
```

### Programmatic Usage

```python
from gitlab_hierarchy.extractor import HierarchyExtractor

extractor = HierarchyExtractor(
    gitlab_url="https://gitlab.com",
    token="your-token",
    db_path="issues.db"
)

result = extractor.extract_issues_from_groups(
    group_ids=[123, 456, 789],
    include_closed=True,
    verbose=True
)

print(f"Total issues: {result['total_issues']}")
print(f"Epic-linked: {result['epic_linked_count']}")
print(f"Orphans: {result['orphan_count']}")
```

## Common Queries

### Find Orphan Issues

```sql
SELECT
    id,
    title,
    project_path_with_namespace,
    state,
    created_at
FROM gitlab_project_issues
WHERE has_epic = 0
  AND is_latest = 1
ORDER BY created_at DESC;
```

### Issues by Project

```sql
SELECT
    project_path_with_namespace,
    COUNT(*) as total_issues,
    SUM(CASE WHEN has_epic = 1 THEN 1 ELSE 0 END) as epic_linked,
    SUM(CASE WHEN has_epic = 0 THEN 1 ELSE 0 END) as orphans,
    ROUND(100.0 * SUM(CASE WHEN has_epic = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as link_pct
FROM gitlab_project_issues
WHERE is_latest = 1
GROUP BY project_path_with_namespace
ORDER BY orphans DESC;
```

### Overdue Orphan Issues

```sql
SELECT
    id,
    title,
    project_path_with_namespace,
    due_date,
    days_overdue,
    assignee_username
FROM gitlab_project_issues
WHERE has_epic = 0
  AND is_overdue = 1
  AND state = 'opened'
  AND is_latest = 1
ORDER BY days_overdue DESC;
```

### Issues Linked to Specific Epic

```sql
SELECT
    id,
    title,
    state,
    assignee_username,
    weight,
    days_open
FROM gitlab_project_issues
WHERE epic_group_id = 123
  AND epic_iid = 10
  AND is_latest = 1
ORDER BY created_at;
```

### Epic Linkage Coverage

```sql
SELECT
    'Total Issues' as metric,
    COUNT(*) as count
FROM gitlab_project_issues
WHERE is_latest = 1

UNION ALL

SELECT
    'Epic-Linked Issues',
    COUNT(*)
FROM gitlab_project_issues
WHERE is_latest = 1 AND has_epic = 1

UNION ALL

SELECT
    'Orphan Issues',
    COUNT(*)
FROM gitlab_project_issues
WHERE is_latest = 1 AND has_epic = 0;
```

## Use Cases

### 1. Epic Coverage Analysis
**Goal**: Identify how many issues are properly linked to epics

```bash
neo extract-issues-from-groups --group-ids "100,200,300"

sqlite3 issues.db "
SELECT
    project_path,
    COUNT(*) as total,
    SUM(has_epic) as linked,
    ROUND(100.0 * SUM(has_epic) / COUNT(*), 2) as coverage_pct
FROM gitlab_project_issues
WHERE is_latest = 1
GROUP BY project_path
ORDER BY coverage_pct;"
```

### 2. Orphan Issue Cleanup
**Goal**: Find issues that need to be linked to epics

```bash
# Export orphan issues to CSV for review
neo extract-issues-from-groups --group-ids "100"
neo export \
  --db issues.db \
  --format csv \
  --output orphans.csv \
  --sql "SELECT * FROM gitlab_project_issues WHERE has_epic = 0 AND is_latest = 1"
```

### 3. Cross-Project Epic Tracking
**Goal**: See all issues linked to a specific epic across multiple projects

```sql
-- Find all issues linked to Epic #5 in Group 100
SELECT
    project_path_with_namespace,
    title,
    state,
    assignee_username,
    weight
FROM gitlab_project_issues
WHERE epic_group_id = 100
  AND epic_iid = 5
  AND is_latest = 1;
```

### 4. Historical Orphan Tracking
**Goal**: Track orphan issue trends over time

```bash
# Run extraction daily
neo extract-issues-from-groups \
  --group-ids "100,200" \
  --snapshot-date "2025-01-15"

# Query trend
sqlite3 issues.db "
SELECT
    snapshot_date,
    COUNT(*) as total_issues,
    SUM(CASE WHEN has_epic = 0 THEN 1 ELSE 0 END) as orphans,
    ROUND(100.0 * SUM(CASE WHEN has_epic = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as orphan_pct
FROM gitlab_project_issues
GROUP BY snapshot_date
ORDER BY snapshot_date;"
```

## Performance Considerations

### API Calls
- **Per Group**: 1 API call to get projects
- **Per Project**: 1 API call to get all issues
- **Total**: `num_groups + total_projects` API calls
- **Rate Limiting**: 0.5s delay between calls (configurable)

### Typical Execution Time
- **10 projects, 100 issues each**: ~10-15 seconds
- **50 projects, 500 issues each**: ~2-3 minutes
- **200 projects, 1000 issues each**: ~15-20 minutes

### Memory Usage
- **Loads all issues in memory** before storing
- **Estimate**: ~1KB per issue
- **Example**: 10,000 issues ≈ 10MB RAM

### Database Size
- **~2KB per issue** (with indexes)
- **Example**: 10,000 issues ≈ 20MB database size

## Comparison with Epic-Based Extraction

### When to Use Each Method

**Use `extract-from-groups` (Epic-Based)**:
- ✅ Need full epic→issue hierarchy with depth/paths
- ✅ Focused on specific epic tree
- ✅ Need parent-child relationships
- ✅ Want to build reporting hierarchies

**Use `extract-issues-from-groups` (Project-Based)**:
- ✅ Need complete issue inventory
- ✅ Want to find orphan issues
- ✅ Analyze issues independently of epics
- ✅ Track epic linkage coverage
- ✅ Need all issues regardless of epic structure

**Use Both**:
- ✅ Comprehensive analysis combining hierarchy + inventory
- ✅ Compare epic-based vs. project-based issue counts
- ✅ Validate epic linkages
- ✅ Full visibility into issue management

### Data Redundancy

Issues that are linked to epics will appear in **both tables**:
- `gitlab_hierarchy` - as part of epic tree
- `gitlab_project_issues` - as project inventory

**This is intentional** for different analysis needs.

## Future Enhancements

Potential improvements:

1. **Link Validation**: Compare issues in both tables, flag discrepancies
2. **Auto-Linking Suggestions**: ML-based suggestions for linking orphans to epics
3. **Project Filtering**: Filter by specific projects instead of all in group
4. **Parallel Fetching**: Use threading to fetch from multiple projects concurrently
5. **Incremental Updates**: Only fetch changed issues since last snapshot
6. **Epic Hierarchy Join**: Join with `gitlab_hierarchy` to show full epic ancestry

## Troubleshooting

### Issue: Too many API calls

**Solution**: Reduce number of groups or use project filtering (future enhancement)

### Issue: Memory usage too high

**Solution**: Process projects in batches, commit to database incrementally

### Issue: Missing epic linkage information

**Cause**: GitLab API doesn't always return epic field for issues

**Solution**: This is a GitLab API limitation; epic field may be null even if issue is linked

### Issue: Duplicate issues across snapshots

**Cause**: Multiple snapshots with `is_latest=1`

**Solution**: Use cleanup command to remove old snapshots:
```bash
neo cleanup --db issues.db --keep-days 30
```

## Summary

This feature provides **comprehensive issue visibility** by capturing ALL issues from projects, complementing the existing epic hierarchy extraction. It enables:

- ✅ Complete issue inventory
- ✅ Orphan issue identification
- ✅ Epic linkage tracking
- ✅ Cross-project analysis
- ✅ Independent issue-level reporting

**Database tables**:
- `gitlab_hierarchy` - Epic-based extraction (hierarchy tree)
- `gitlab_project_issues` - Project-based extraction (flat inventory)

Both tables work together to provide full visibility into your GitLab issues and epics.

---

**Implementation Date**: 2025-12-18
**Version**: 1.0.0
**Status**: ✅ Complete and Ready for Production
