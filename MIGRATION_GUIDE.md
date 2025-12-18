# Migration Guide: Using In-Memory Extraction Method

## Problem

The original `extract` command uses GitLab's `group.epics.list(parent_id=...)` API to filter child epics. However, **this filter doesn't work correctly in some GitLab versions** - it returns ALL epics in the group instead of just the children of the specified parent epic.

This causes:
- Incorrect hierarchy relationships
- Potential infinite loops (despite cycle detection)
- Performance issues from processing unnecessary epics
- Incorrect metrics and counts

## Solution

The new `extract-from-groups` command implements a more reliable approach:

1. **Fetch all epics upfront** from specified groups (no filtering)
2. **Build hierarchy in-memory** using each epic's `parent_id` field
3. **Link issues** to their parent epics as before

This approach is:
- ✅ **More reliable** - doesn't depend on broken API filtering
- ✅ **Better for multi-group hierarchies** - naturally handles cross-group parent relationships
- ✅ **Fewer API calls** - one call per group instead of one per epic
- ✅ **Easier to debug** - can inspect all epics before building hierarchy

## Usage Comparison

### Old Method (may not work correctly)

```bash
# Extract using GitLab's parent_id filter
gitlab-hierarchy extract \
  --group-id 123 \
  --epic-iid 10 \
  --db hierarchy.db
```

### New Method (recommended)

```bash
# Extract using in-memory parent_id relationships
gitlab-hierarchy extract-from-groups \
  --group-ids "123,456,789" \
  --root-group-id 123 \
  --epic-iid 10 \
  --db hierarchy.db
```

## Key Differences

| Parameter | Old Command | New Command | Notes |
|-----------|-------------|-------------|-------|
| Command | `extract` | `extract-from-groups` | New command name |
| Groups | `--group-id` (single) | `--group-ids` (multiple) | Comma-separated list |
| Root Group | Same as `--group-id` | `--root-group-id` (separate) | Which group contains root epic |
| Epic IID | `--epic-iid` | `--epic-iid` | Same parameter |

## When to Use Each Method

### Use `extract-from-groups` (new method) when:

- ✅ GitLab's parent_id filter is not working correctly
- ✅ Your hierarchy spans multiple groups
- ✅ You need to ensure all epics are discovered
- ✅ You want more reliable results
- ✅ **Recommended for all use cases**

### Use `extract` (old method) when:

- ⚠️ You're certain GitLab's parent_id filter works in your version
- ⚠️ You have a very large single-group hierarchy and memory is limited
- ⚠️ You're maintaining backward compatibility with existing scripts

## Detailed Examples

### Example 1: Single Group Hierarchy

```bash
# Root epic in group 123
gitlab-hierarchy extract-from-groups \
  --group-ids "123" \
  --root-group-id 123 \
  --epic-iid 1 \
  --db myproject.db \
  --verbose
```

### Example 2: Multi-Group Hierarchy

```bash
# Root epic in group 100, with child epics in groups 100, 200, 300
gitlab-hierarchy extract-from-groups \
  --group-ids "100,200,300" \
  --root-group-id 100 \
  --epic-iid 5 \
  --db myproject.db \
  --gitlab-url "https://gitlab.example.com" \
  --token "glpat-xxxxxxxxxxxx"
```

### Example 3: With Environment Variables

```bash
# Set token via environment variable
export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"

gitlab-hierarchy extract-from-groups \
  --group-ids "123,456" \
  --root-group-id 123 \
  --epic-iid 10 \
  --max-depth 15 \
  --no-include-closed
```

### Example 4: Scheduled Daily Extraction

```bash
#!/bin/bash
# daily_extract.sh

export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"

gitlab-hierarchy extract-from-groups \
  --group-ids "100,200,300,400" \
  --root-group-id 100 \
  --epic-iid 1 \
  --db "hierarchy_$(date +%Y%m%d).db" \
  --snapshot-date "$(date +%Y-%m-%d)" \
  --verbose

# Cleanup old snapshots
gitlab-hierarchy cleanup --db hierarchy.db --keep-days 90
```

## Migration Steps

### Step 1: Identify Your Group IDs

Find all groups that might contain epics in your hierarchy:

```bash
# List your GitLab groups via API
curl --header "PRIVATE-TOKEN: glpat-xxxx" \
  "https://gitlab.com/api/v4/groups?per_page=100"
```

Or check the GitLab UI to note group IDs.

### Step 2: Test with New Command

Run the new command with your group IDs:

```bash
gitlab-hierarchy extract-from-groups \
  --group-ids "GROUP_ID_1,GROUP_ID_2,GROUP_ID_3" \
  --root-group-id ROOT_GROUP_ID \
  --epic-iid ROOT_EPIC_IID \
  --db test_hierarchy.db \
  --verbose
```

### Step 3: Compare Results

Compare the results with the old method:

```sql
-- Check epic count
SELECT COUNT(*) FROM gitlab_hierarchy WHERE type = 'epic';

-- Check hierarchy depth
SELECT MAX(depth) FROM gitlab_hierarchy;

-- Check for orphaned epics (should be in hierarchy)
SELECT * FROM gitlab_hierarchy WHERE parent_id IS NULL AND depth > 0;

-- Check parent-child relationships
SELECT parent_id, COUNT(*) as child_count
FROM gitlab_hierarchy
WHERE parent_id IS NOT NULL
GROUP BY parent_id;
```

### Step 4: Update Your Scripts

Replace `extract` with `extract-from-groups` in your automation scripts.

## Troubleshooting

### Issue: Root epic not found

```
Error: Root epic 10 not found in group 123
```

**Solution**: Ensure the root group ID is included in the `--group-ids` list:

```bash
# Make sure 123 is in the group-ids list
--group-ids "123,456,789" --root-group-id 123
```

### Issue: Missing child epics

```
Note: 50 epics were not part of the root epic's hierarchy
```

**Explanation**: This is normal. The command fetches ALL epics from the specified groups, but only includes epics that are actually descendants of the root epic in the hierarchy. Epics that aren't connected to your root epic are reported but not included.

**Action**: If you expected these epics to be in the hierarchy, verify:
1. The epic's parent_id is set correctly in GitLab
2. There's no circular reference preventing inclusion
3. The epic is within the max-depth limit (default: 20)

### Issue: Memory usage is high

```
MemoryError: Unable to allocate array
```

**Solution**: The in-memory method loads all epics at once. For very large GitLab instances:
1. Reduce the number of groups in `--group-ids` to only essential ones
2. Use the old `extract` command if GitLab's filter works in your version
3. Increase available system memory

### Issue: Performance is slow

**Expected**: The new method makes fewer API calls but processes more data in-memory:
- **Faster** for hierarchies with many levels (fewer API calls)
- **Similar** for flat hierarchies
- **Slower** only for initial epic fetching if you specify many large groups

## API Method Comparison

### Old Method (`build_from_epic`)

```python
# Recursively fetch children for each epic
for each epic:
    children = group.epics.list(parent_id=epic.id)  # ⚠️ May return ALL epics
    for child in children:
        recursively process child
```

### New Method (`build_from_groups`)

```python
# Fetch all epics once
all_epics = []
for group_id in group_ids:
    all_epics.extend(group.epics.list())  # ✅ Get all epics

# Build hierarchy in-memory
epics_by_id = {epic.id: epic for epic in all_epics}
for epic in epics_by_id.values():
    if epic.parent_id == current_epic.id:
        add_to_hierarchy(epic)  # ✅ Filter in-memory
```

## Additional Resources

- [GitLab Epics API Documentation](https://docs.gitlab.com/ee/api/epics.html)
- [Project README](README.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)

## Support

If you encounter issues with the new method, please:

1. Check this migration guide first
2. Review the logs with `--verbose` flag
3. Verify your GitLab token has appropriate permissions
4. Open an issue on GitHub with:
   - GitLab version
   - Command used
   - Error message
   - Output with `--verbose`
