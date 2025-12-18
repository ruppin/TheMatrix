# Architecture & Design

This document explains the architecture and design decisions behind the GitLab Hierarchy Extractor.

## Overview

The tool extracts GitLab epic and issue hierarchies into a SQLite database for analysis and reporting. It's designed to be:

- **Simple**: Single database table, straightforward schema
- **Comprehensive**: Captures 60+ fields from epics and issues
- **Flexible**: Supports custom label patterns and queries
- **Maintainable**: Modular architecture with clear separation of concerns
- **Testable**: High test coverage with mocked dependencies

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI Layer (cli.py)                       │
│  Commands: extract, stats, cleanup, export, query               │
└─────────────────────────────────────────┬───────────────────────┘
                                          │
┌─────────────────────────────────────────▼───────────────────────┐
│                   Orchestrator (extractor.py)                   │
│  Coordinates extraction workflow across components              │
└──────┬──────────────────┬─────────────────┬─────────────────────┘
       │                  │                 │
       │                  │                 │
┌──────▼─────┐   ┌────────▼────────┐   ┌───▼──────────┐
│  GitLab    │   │   Hierarchy     │   │    Label     │
│  Client    │   │   Builder       │   │   Parser     │
│            │   │                 │   │              │
│ API Calls  │   │ Tree Traversal  │   │ Normalize    │
└──────┬─────┘   └────────┬────────┘   └───┬──────────┘
       │                  │                 │
       │                  │                 │
       └──────────────────┴─────────────────┘
                          │
                ┌─────────▼──────────┐
                │   Database Layer   │
                │   (database.py)    │
                │                    │
                │   SQLite Storage   │
                └────────────────────┘
```

## Component Design

### 1. CLI Layer (`cli.py`)

**Purpose**: User interface using Click framework

**Commands**:
- `extract`: Main extraction workflow
- `stats`: Show database statistics
- `cleanup`: Remove old snapshots
- `export`: Export to CSV/JSON
- `query`: Execute custom SQL

**Design Decisions**:
- Click for rich CLI with auto-help generation
- Environment variables for configuration (12-factor app)
- Sensible defaults for all parameters
- Progressive disclosure (basic → advanced options)

### 2. Orchestrator (`extractor.py`)

**Purpose**: Coordinate the extraction workflow

**Responsibilities**:
- Initialize all components
- Execute 4-phase extraction:
  1. Discover hierarchy (via builder)
  2. Parse labels (via parser)
  3. Store to database
  4. Calculate statistics
- Manage resource lifecycle (context manager)

**Design Decisions**:
- Single entry point for extraction
- Dependency injection for testability
- Context manager for automatic cleanup
- Progress tracking with tqdm (optional)

### 3. GitLab Client (`gitlab_client.py`)

**Purpose**: Wrap python-gitlab library with hierarchy-specific methods

**Key Methods**:
- `get_epic()`: Fetch single epic
- `get_child_epics()`: Get children using parent_id filter
- `get_epic_issues()`: Get all issues in epic
- `get_issue()`: Fetch single issue
- `get_issue_links()`: Get blocking relationships

**Design Decisions**:
- Wrap python-gitlab instead of raw API calls (better error handling)
- Use `parent_id` filter instead of `epic.epics` attribute (works around API limitations)
- Rate limiting built-in (configurable delay)
- Convert API objects to dicts immediately (easier to work with)
- Handle missing permissions gracefully (log + continue)

### 4. Hierarchy Builder (`hierarchy_builder.py`)

**Purpose**: Traverse GitLab hierarchy and build tree structure

**Algorithm**:
```python
def build_from_epic(group_id, epic_iid, max_depth):
    1. Fetch root epic
    2. Initialize visited sets (cycle detection)
    3. Recursively traverse:
       a. Get child epics (if depth < max_depth)
       b. Get issues in epic
       c. For each child epic: recurse
    4. Calculate relationships:
       - Parent-child mappings
       - Child counts (epic + issue)
       - Descendant counts (recursive)
    5. Calculate derived metrics:
       - days_open
       - is_overdue
       - completion_pct
    6. Return flat list with hierarchy metadata
```

**Design Decisions**:
- **Flat output** instead of nested tree (easier for database storage)
- **Cycle detection** using visited sets (prevents infinite loops)
- **Depth tracking** for hierarchy analysis
- **Hierarchy path** as breadcrumb trail (e.g., "epic:1/epic:2/issue:3")
- **Filter closed items** option for focusing on active work
- **Max depth limit** to prevent overwhelming large hierarchies

### 5. Label Parser (`label_parser.py`)

**Purpose**: Normalize labels into structured columns

**Label Format**: `category:value` or `category-value`

**Default Categories**:
- priority (critical, high, medium, low)
- type (epic, feature, bug, task)
- status (backlog, todo, in-progress, done)
- team (backend, frontend, devops, etc.)
- component (api, ui, database, etc.)

**Custom Categories**: Automatically stored in `label_custom_1/2/3`

**Design Decisions**:
- **Pattern matching** with regex for flexibility
- **First match wins** when multiple labels have same category
- **Case-insensitive** matching for category prefix
- **Extensible** via custom patterns
- **Discovery mode** tracks unknown categories
- **Overflow handling** for categories beyond predefined slots

### 6. Database Layer (`database.py`)

**Purpose**: All SQLite operations

**Schema Design**:

**Identity Fields**:
- `id` (primary key): "epic:123#10" or "issue:456#5"
- `type`: 'epic' or 'issue'
- `iid`: Internal ID within group/project
- `group_id`, `project_id`: Container identifiers

**Hierarchy Fields**:
- `parent_id`: Direct parent's ID
- `root_id`: Top-level epic's ID
- `depth`: 0 = root, 1 = child, 2 = grandchild, etc.
- `hierarchy_path`: Full path from root
- `child_epic_count`, `child_issue_count`: Direct children
- `descendant_count`: All descendants (recursive)

**Core Attributes**:
- `title`, `description`, `state`, `web_url`
- `author_*`, `assignee_*`, `milestone_title`
- `labels` (original JSON array)

**Normalized Labels** (from label parser):
- `label_priority`, `label_type`, `label_status`
- `label_team`, `label_component`
- `label_custom_1/2/3` for unknown categories

**Dates**:
- `created_at`, `updated_at`, `closed_at`
- `due_date`, `start_date`, `end_date`

**Derived Metrics**:
- `days_open`: Days since creation
- `days_to_close`: Days from creation to closure
- `is_overdue`: Boolean flag
- `completion_pct`: Percentage of closed child issues

**Relationships** (JSON):
- `blocks`: Issue IIDs this blocks
- `blocked_by`: Issue IIDs blocking this
- `related_issues`, `related_merge_requests`

**Versioning**:
- `snapshot_date`: When data was extracted
- `data_version`: Monotonic version number
- `is_latest`: Boolean flag for current snapshot

**Design Decisions**:
- **Single table** instead of separate epic/issue tables (simpler queries, easier joins)
- **Composite ID** as primary key (unique across types)
- **JSON columns** for relationships (flexible, but queryable with JSON functions)
- **Denormalized data** (e.g., child counts) for query performance
- **Snapshot versioning** for historical analysis
- **10 indexes** for common query patterns
- **NULL-friendly** schema (many fields optional)

### 7. Data Models (`models.py`)

**Purpose**: Define schema and provide data classes

**Classes**:
- `HierarchyItem`: Base class with common fields
- `Epic`: Epic-specific fields (start_date, end_date)
- `Issue`: Issue-specific fields (weight, time tracking)

**Design Decisions**:
- **Schema as SQL constant** for easy review
- **Data classes** with `to_dict()` for serialization
- **Type hints** for better IDE support
- **Validation** in constructors (future enhancement)

## Key Design Patterns

### 1. Flat Hierarchy in Relational Database

**Challenge**: GitLab hierarchies are tree structures, but SQL databases are relational.

**Solution**: Store flat table with hierarchy metadata:
- `parent_id` for parent-child relationships
- `depth` for level in tree
- `hierarchy_path` for full ancestry
- `root_id` for grouping all items in same tree

**Benefits**:
- Easy to query ("get all items in epic X")
- Standard SQL joins work
- No recursive CTEs needed for most queries
- Fast aggregations

**Tradeoffs**:
- Denormalized data (child counts)
- Must recalculate metrics on update

### 2. Snapshot Versioning

**Challenge**: Track changes over time for trending analysis.

**Solution**: Store multiple snapshots with versioning:
- Each extraction gets unique `snapshot_date`
- `is_latest` flag marks current snapshot
- Old snapshots marked not-latest but retained
- Cleanup removes snapshots older than N days

**Benefits**:
- Historical trending (burndown, velocity)
- Compare snapshots to see changes
- No complex change tracking logic
- Simple to understand and query

**Tradeoffs**:
- Database grows with each snapshot
- Must manage cleanup policy
- Cannot track fine-grained changes

### 3. Label Normalization

**Challenge**: GitLab labels are free-form strings, hard to query/filter.

**Solution**: Parse labels into structured columns:
- Match patterns like "priority:high"
- Extract category and value
- Store in dedicated columns (`label_priority`, etc.)
- Keep original labels in JSON array

**Benefits**:
- Easy SQL filtering ("WHERE label_priority = 'high'")
- Standard aggregations ("GROUP BY label_team")
- Consistent data across teams
- Discoverable categories

**Tradeoffs**:
- Requires label convention ("category:value")
- Limited to predefined categories (+ 3 custom slots)
- Must reprocess on label pattern changes

### 4. Derived Metrics at Extraction Time

**Challenge**: Calculate metrics like completion %, days open, overdue status.

**Solution**: Calculate during extraction, not at query time:
- Compute metrics in `hierarchy_builder.py`
- Store as columns in database
- Update on each extraction

**Benefits**:
- Fast queries (no computation needed)
- Consistent calculations
- Easy to understand schema
- Simple SQL for reporting

**Tradeoffs**:
- Must re-extract to update metrics
- Cannot change calculation logic retroactively
- More database storage

### 5. Modular Architecture with Dependency Injection

**Challenge**: Make code testable and maintainable.

**Solution**: Separate concerns into modules, inject dependencies:
- Each module has single responsibility
- Components accept dependencies in constructor
- Use interfaces (duck typing) not concrete classes
- Mock dependencies in tests

**Benefits**:
- Easy to test in isolation
- Easy to swap implementations
- Clear responsibilities
- Low coupling

**Example**:
```python
# Extractor accepts dependencies
extractor = HierarchyExtractor(
    gitlab_url=url,
    token=token,
    db_path=path,
    label_patterns=custom_patterns  # injectable
)

# Easy to mock in tests
mock_client = Mock()
builder = HierarchyBuilder(mock_client)
```

## Performance Considerations

### API Rate Limiting

- Default: 0.5s delay between requests
- Configurable via environment variable
- Necessary for GitLab.com (10 req/sec limit)

### Database Performance

- **Indexes**: 10 indexes on commonly queried fields
- **Batch inserts**: Insert items in batches (100-1000)
- **Transactions**: Wrap batch operations
- **Prepared statements**: Use parameterized queries

### Memory Usage

- **Streaming**: Process items as discovered (don't load all in memory)
- **Flat structure**: No deep nesting in data structures
- **Cleanup**: Delete old snapshots regularly

## Testing Strategy

### Unit Tests

- Test each module in isolation
- Mock all external dependencies
- Focus on business logic
- Fast execution (< 1s per test)

### Integration Tests

- Test component interactions
- Use temporary databases
- Mock only GitLab API
- Slower but more realistic

### Test Fixtures

- Shared fixtures in `conftest.py`
- Reusable mock data
- Temporary database creation
- Cleanup after tests

### Coverage Goals

- **Minimum**: 80% line coverage
- **Target**: 90% line coverage
- Focus on critical paths
- Skip trivial code (getters, setters)

## Security Considerations

### API Token Handling

- **Environment variables** for tokens (never hardcoded)
- **No logging** of tokens
- **Masked in error messages**
- **File permissions** on .env files (0600)

### SQL Injection

- **Parameterized queries** everywhere
- No string concatenation for SQL
- Validate user input (e.g., table names in export)

### Data Privacy

- Tool stores data locally (no external transmission)
- User controls database location
- No telemetry or tracking
- GDPR-friendly (data stays local)

## Future Enhancements

### Planned Features

1. **Incremental Updates**
   - Only fetch changed items since last extraction
   - Use `updated_since` API parameter
   - Compare with last snapshot date

2. **Parallel Extraction**
   - Process multiple epics concurrently
   - Thread pool for API calls
   - Batch database inserts

3. **Change Detection**
   - Compare snapshots to detect changes
   - Track field-level changes
   - Generate change reports

4. **Advanced Queries**
   - Pre-built report templates
   - Burndown chart data
   - Velocity calculations
   - Risk analysis

5. **Export Formats**
   - Excel with multiple sheets
   - JSON with nested structure
   - GraphQL-style queries

6. **Web UI**
   - Browse hierarchy interactively
   - Visual tree representation
   - Dashboard with charts
   - Filter and search

### Extensibility Points

- **Custom label patterns**: Add via configuration
- **Custom metrics**: Extend `HierarchyBuilder`
- **Custom exports**: Add new formats in CLI
- **Custom queries**: SQL + pandas
- **Plugins**: Hook system for extensions

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on:
- Setting up development environment
- Running tests
- Code style
- Submitting pull requests

## References

- [GitLab API Documentation](https://docs.gitlab.com/ee/api/)
- [python-gitlab Library](https://python-gitlab.readthedocs.io/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Click Framework](https://click.palletsprojects.com/)
