# GitLab Epic & Issue Hierarchy Extractor

A production-ready Python tool that traverses GitLab epic hierarchies starting from a root epic, captures all child epics and their issues recursively down to leaf-level issues, and stores comprehensive data in a SQLite database optimized for reporting and analytics.

## Features

- ✅ **Complete Hierarchy Extraction**: Recursively traverse epics → child epics → issues
- ✅ **Reliable In-Memory Method**: Fetch all epics upfront, build hierarchy from parent_id (recommended)
- ✅ **Multi-Group Support**: Handle epic hierarchies spanning multiple GitLab groups
- ✅ **Comprehensive Data Capture**: All epic and issue attributes from GitLab API
- ✅ **Smart Label Parsing**: Auto-detect and normalize labels into columns
- ✅ **Relationship Tracking**: Parent-child, blocking, and related links
- ✅ **Historical Snapshots**: Track changes over time
- ✅ **Derived Metrics**: Completion %, days open, overdue status, etc.
- ✅ **Performance Optimized**: Handle 1000+ items efficiently
- ✅ **CLI Interface**: Easy-to-use command-line tool

## Installation

### From Source

```bash
git clone <repository-url>
cd pygitproject
pip install -e .
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Set GitLab Token

```bash
export GITLAB_TOKEN="your_gitlab_token_here"
```

### 2. Extract Hierarchy (Recommended Method)

```bash
neo extract-from-groups \
  --group-ids "123,456" \
  --root-group-id 123 \
  --epic-iid 10 \
  --db hierarchy.db
```

Or use the legacy method:

```bash
neo extract \
  --group-id 123 \
  --epic-iid 10 \
  --db hierarchy.db
```

### 3. View Statistics

```bash
neo stats --db hierarchy.db
```

### 4. Export to CSV

```bash
neo export \
  --db hierarchy.db \
  --format csv \
  --output results.csv
```

## Usage

### Extract from Groups Command (Recommended)

**NEW**: Extract hierarchy using reliable in-memory method that fetches all epics upfront:

```bash
# Basic usage - single group
neo extract-from-groups \
  --group-ids "123" \
  --root-group-id 123 \
  --epic-iid 10

# Multi-group hierarchy
neo extract-from-groups \
  --group-ids "123,456,789" \
  --root-group-id 123 \
  --epic-iid 10 \
  --db hierarchy.db \
  --gitlab-url https://gitlab.company.com \
  --verbose
```

**Why use this command?**
- ✅ More reliable - doesn't depend on GitLab's parent_id filter (which may not work correctly)
- ✅ Better for multi-group hierarchies
- ✅ Fewer API calls
- ✅ Easier to debug

**Options:**
- `--group-ids`: Comma-separated list of group IDs to fetch epics from (required)
- `--root-group-id`: Group ID containing the root epic (required)
- `--epic-iid`: Root epic IID (required)
- `--db`: SQLite database path (default: `hierarchy.db`)
- `--gitlab-url`: GitLab instance URL (default: `https://gitlab.com`)
- `--token`: GitLab token (or set `GITLAB_TOKEN` env var)
- `--snapshot-date`: Snapshot date in YYYY-MM-DD format (default: today)
- `--include-closed/--no-include-closed`: Include closed items (default: yes)
- `--max-depth`: Maximum hierarchy depth (default: 20)
- `--verbose`: Show progress bars and debug info

📖 **See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for detailed comparison and migration instructions**

### Extract Command (Legacy)

Extract complete hierarchy from a root epic using GitLab's API filtering:

> ⚠️ **Note**: This command relies on GitLab's `parent_id` filter which may not work correctly in some GitLab versions. Consider using `extract-from-groups` instead.

```bash
# Basic usage
neo extract --group-id 123 --epic-iid 10

# With all options
neo extract \
  --group-id 123 \
  --epic-iid 10 \
  --db hierarchy.db \
  --gitlab-url https://gitlab.company.com \
  --token $GITLAB_TOKEN \
  --snapshot-date 2024-01-15 \
  --include-closed \
  --max-depth 10 \
  --verbose
```

**Options:**
- `--group-id`: Group ID where root epic exists (required)
- `--epic-iid`: Epic IID (required)
- Other options same as `extract-from-groups`

### Stats Command

Show database statistics:

```bash
# Overall stats
neo stats --db hierarchy.db

# Stats for specific root epic
neo stats --db hierarchy.db --root-id "epic:123#10"
```

### Export Command

Export data to CSV or JSON:

```bash
# Export all data to CSV
neo export --db hierarchy.db --format csv --output data.csv

# Export specific root to JSON
neo export \
  --db hierarchy.db \
  --format json \
  --output data.json \
  --root-id "epic:123#10"
```

### Cleanup Command

Remove old snapshots:

```bash
# Keep only last 90 days
neo cleanup --db hierarchy.db --keep-days 90
```

### Query Command

Execute custom SQL queries:

```bash
neo query --db hierarchy.db --sql "SELECT COUNT(*) FROM gitlab_hierarchy WHERE state='opened'"
```

## Database Schema

The tool creates a single table `gitlab_hierarchy` with comprehensive fields:

**Key Fields:**
- `id` - Unique identifier (e.g., "epic:123#10" or "issue:456#20")
- `type` - 'epic' or 'issue'
- `parent_id` - Parent item ID
- `root_id` - Top-most epic ID
- `depth` - Hierarchy level (0=root)
- `title`, `description`, `state` - Core attributes
- `labels_raw` - All labels as JSON
- `label_priority`, `label_type`, etc. - Parsed label columns
- `days_open`, `is_overdue`, `completion_pct` - Derived metrics
- `snapshot_date` - When data was captured
- `is_latest` - Boolean flag for current snapshot

See `gitlab_hierarchy/models.py` for complete schema.

## Sample Queries

### Epic Completion Status

```sql
SELECT
    title,
    completion_pct,
    child_count,
    descendant_count
FROM gitlab_hierarchy
WHERE type = 'epic' AND is_latest = TRUE
ORDER BY completion_pct ASC;
```

### Overdue Items by Assignee

```sql
SELECT
    assignee_username,
    COUNT(*) as overdue_count,
    SUM(story_points) as overdue_points
FROM gitlab_hierarchy
WHERE is_overdue = TRUE AND state = 'opened' AND is_latest = TRUE
GROUP BY assignee_username;
```

### Bottleneck Detection

```sql
SELECT
    id,
    title,
    blocks_count,
    days_open,
    state
FROM gitlab_hierarchy
WHERE blocks_count > 0 AND state = 'opened' AND is_latest = TRUE
ORDER BY blocks_count DESC, days_open DESC;
```

### Team Workload by Labels

```sql
SELECT
    label_team,
    COUNT(*) as items,
    SUM(story_points) as total_points,
    AVG(days_open) as avg_age
FROM gitlab_hierarchy
WHERE state = 'opened' AND type = 'issue' AND is_latest = TRUE
GROUP BY label_team;
```

## Configuration

### Environment Variables

```bash
# Required
export GITLAB_TOKEN="glpat-xxxxxxxxxxxxx"

# Optional
export GITLAB_URL="https://gitlab.company.com"
```

### Label Patterns

The tool auto-detects label patterns like:
- `priority:high` → `label_priority = "high"`
- `type:bug` → `label_type = "bug"`
- `team:backend` → `label_team = "backend"`
- `status:blocked` → `label_status = "blocked"`
- `component:api` → `label_component = "api"`

Custom categories are automatically captured in `label_custom_1`, `label_custom_2`, `label_custom_3`.

## Python API

Use the tool programmatically:

```python
from gitlab_hierarchy import HierarchyExtractor

# Initialize extractor
extractor = HierarchyExtractor(
    gitlab_url='https://gitlab.com',
    token='your_token',
    db_path='hierarchy.db'
)

# Extract hierarchy
result = extractor.extract(
    group_id=123,
    epic_iid=10,
    include_closed=True,
    max_depth=20,
    verbose=True
)

print(f"Extracted {result['total_items']} items")

# Get statistics
stats = extractor.get_stats()

# Cleanup
extractor.close()
```

## Architecture

```
gitlab_hierarchy/
├── __init__.py              # Package initialization
├── cli.py                   # CLI commands (click)
├── extractor.py             # Main orchestrator
├── models.py                # Database schema
├── database.py              # SQLite operations
├── gitlab_client.py         # GitLab API wrapper
├── label_parser.py          # Label normalization
└── hierarchy_builder.py     # Tree traversal logic
```

## Development

### Run Tests

```bash
pytest tests/
pytest --cov=gitlab_hierarchy
```

### Code Formatting

```bash
black gitlab_hierarchy/
flake8 gitlab_hierarchy/
mypy gitlab_hierarchy/
```

## Troubleshooting

### Authentication Error

```
Error: GitLab authentication failed
```

**Solution**: Check that your `GITLAB_TOKEN` is valid and has `api` or `read_api` scope.

### Epics Not Available

```
Error: Epics are only available in GitLab Premium/Ultimate
```

**Solution**: Epics require GitLab Premium or Ultimate tier. The tool won't work with Free tier for epic-based hierarchies.

### Rate Limit Errors

**Solution**: Increase the rate limit delay:

```python
extractor = HierarchyExtractor(
    gitlab_url=url,
    token=token,
    db_path=db_path,
    rate_limit_delay=1.0  # Increase from default 0.5
)
```

## License

MIT License

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

- **Issues**: Open an issue on GitHub
- **Documentation**: See `docs/` directory
- **Examples**: See `examples/` directory

---

**Built with ❤️ for GitLab project management and reporting**
