# GitLab Management Reporting - SQL Queries & Best Practices

This guide provides comprehensive SQL queries for GitLab management across multiple dimensions, plus best practices for organizing Epics, Issues, and Labels to enable effective reporting.

## Table of Contents

1. [Portfolio Management & Strategic Planning](#1-portfolio-management--strategic-planning)
2. [Progress Tracking & Burndown](#2-progress-tracking--burndown)
3. [Risk & Dependency Management](#3-risk--dependency-management)
4. [Scope & Change Management](#4-scope--change-management)
5. [Resource Allocation & Capacity](#5-resource-allocation--capacity)
6. [Compliance & Audit](#6-compliance--audit)
7. [Forecasting & Estimation](#7-forecasting--estimation)
8. [Team Performance & Metrics](#8-team-performance--metrics)
9. [Best Practices for Epic & Issue Organization](#best-practices-for-epic--issue-organization)
10. [Label Management Strategy](#label-management-strategy)

---

## 1. Portfolio Management & Strategic Planning

### 1.1 Portfolio Overview - All Initiatives

```sql
-- Get high-level view of all strategic initiatives (Level 1 epics)
SELECT
    title,
    state,
    child_count,
    descendant_count,
    completion_pct,
    start_date,
    end_date,
    label_priority,
    label_status,
    CASE
        WHEN end_date < DATE('now') AND state = 'opened' THEN 'Overdue'
        WHEN end_date >= DATE('now') AND state = 'opened' THEN 'On Track'
        WHEN state = 'closed' THEN 'Completed'
        ELSE 'Not Started'
    END as health_status,
    web_url
FROM gitlab_hierarchy
WHERE type = 'epic'
    AND depth = 1
    AND is_latest = 1
ORDER BY
    CASE label_priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
        ELSE 5
    END,
    end_date;
```

### 1.2 Strategic Alignment Matrix

```sql
-- Map initiatives to strategic themes/objectives
SELECT
    label_theme as strategic_theme,
    label_quarter as planning_quarter,
    COUNT(DISTINCT id) as initiative_count,
    SUM(descendant_count) as total_work_items,
    ROUND(AVG(completion_pct), 1) as avg_completion,
    SUM(CASE WHEN state = 'closed' THEN 1 ELSE 0 END) as completed_initiatives,
    SUM(CASE WHEN state = 'opened' THEN 1 ELSE 0 END) as active_initiatives
FROM gitlab_hierarchy
WHERE type = 'epic'
    AND depth = 1
    AND is_latest = 1
GROUP BY label_theme, label_quarter
ORDER BY label_quarter, strategic_theme;
```

### 1.3 Investment by Business Area

```sql
-- Calculate effort investment by business area
SELECT
    label_business_area,
    COUNT(DISTINCT CASE WHEN type = 'epic' AND depth = 1 THEN id END) as epics,
    COUNT(DISTINCT CASE WHEN type = 'issue' THEN id END) as issues,
    SUM(CASE WHEN type = 'issue' THEN COALESCE(weight, 0) END) as total_story_points,
    ROUND(100.0 * SUM(CASE WHEN type = 'issue' THEN COALESCE(weight, 0) END) /
        (SELECT SUM(COALESCE(weight, 0)) FROM gitlab_hierarchy WHERE type = 'issue' AND is_latest = 1), 2) as pct_of_total_effort
FROM gitlab_hierarchy
WHERE is_latest = 1
GROUP BY label_business_area
ORDER BY total_story_points DESC;
```

### 1.4 Multi-Quarter Roadmap View

```sql
-- Roadmap showing initiatives across quarters
SELECT
    label_quarter,
    label_theme,
    title,
    label_priority,
    start_date,
    end_date,
    completion_pct,
    state,
    child_count as deliverables
FROM gitlab_hierarchy
WHERE type = 'epic'
    AND depth = 1
    AND is_latest = 1
    AND label_quarter IS NOT NULL
ORDER BY
    label_quarter,
    CASE label_priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END,
    title;
```

---

## 2. Progress Tracking & Burndown

### 2.1 Epic Progress Dashboard

```sql
-- Current progress of all active epics
SELECT
    id,
    title,
    depth,
    child_count,
    descendant_count,
    completion_pct,
    state,
    CASE
        WHEN completion_pct >= 90 THEN 'Near Completion'
        WHEN completion_pct >= 60 THEN 'On Track'
        WHEN completion_pct >= 30 THEN 'In Progress'
        WHEN completion_pct > 0 THEN 'Started'
        ELSE 'Not Started'
    END as progress_status,
    label_status,
    assignee_username as epic_owner
FROM gitlab_hierarchy
WHERE type = 'epic'
    AND state = 'opened'
    AND is_latest = 1
ORDER BY depth, completion_pct ASC;
```

### 2.2 Story Point Burndown (Current Snapshot)

```sql
-- Burndown analysis by week
WITH weekly_data AS (
    SELECT
        DATE(created_at, 'weekday 0', '-6 days') as week_start,
        SUM(CASE WHEN state = 'closed' THEN COALESCE(weight, 0) ELSE 0 END) as points_completed,
        SUM(COALESCE(weight, 0)) as total_points
    FROM gitlab_hierarchy
    WHERE type = 'issue'
        AND is_latest = 1
        AND root_id = 'epic:123#10'  -- Replace with your root epic
    GROUP BY week_start
)
SELECT
    week_start,
    points_completed,
    total_points,
    total_points - points_completed as remaining_points,
    ROUND(100.0 * points_completed / NULLIF(total_points, 0), 2) as completion_pct
FROM weekly_data
ORDER BY week_start;
```

### 2.3 Velocity Tracking (Requires Historical Snapshots)

```sql
-- Calculate team velocity over time (requires multiple snapshots)
SELECT
    snapshot_date,
    COUNT(DISTINCT CASE WHEN state = 'closed' AND type = 'issue' THEN id END) as issues_closed,
    SUM(CASE WHEN state = 'closed' AND type = 'issue' THEN COALESCE(weight, 0) ELSE 0 END) as points_completed,
    ROUND(AVG(CASE WHEN state = 'closed' AND type = 'issue' THEN days_to_close END), 1) as avg_cycle_time
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND label_team = 'backend'  -- Filter by team
GROUP BY snapshot_date
ORDER BY snapshot_date DESC
LIMIT 10;
```

### 2.4 Milestone Burndown

```sql
-- Progress by milestone
SELECT
    milestone_title,
    COUNT(*) as total_issues,
    SUM(CASE WHEN state = 'closed' THEN 1 ELSE 0 END) as closed_issues,
    SUM(CASE WHEN state = 'opened' THEN 1 ELSE 0 END) as open_issues,
    SUM(COALESCE(weight, 0)) as total_points,
    SUM(CASE WHEN state = 'closed' THEN COALESCE(weight, 0) ELSE 0 END) as completed_points,
    ROUND(100.0 * SUM(CASE WHEN state = 'closed' THEN 1 ELSE 0 END) / COUNT(*), 2) as completion_pct
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND is_latest = 1
    AND milestone_title IS NOT NULL
GROUP BY milestone_title
ORDER BY milestone_title;
```

---

## 3. Risk & Dependency Management

### 3.1 At-Risk Items Identification

```sql
-- Identify high-risk items based on multiple factors
SELECT
    id,
    title,
    type,
    label_priority,
    is_overdue,
    days_overdue,
    assignee_username,
    label_status,
    CASE
        WHEN is_overdue = 1 AND label_priority IN ('critical', 'high') THEN 'HIGH RISK'
        WHEN is_overdue = 1 THEN 'MEDIUM RISK'
        WHEN days_open > 90 AND state = 'opened' THEN 'MEDIUM RISK'
        WHEN label_status = 'blocked' THEN 'HIGH RISK'
        WHEN assignee_username IS NULL AND label_priority = 'high' THEN 'MEDIUM RISK'
        ELSE 'LOW RISK'
    END as risk_level,
    CASE
        WHEN is_overdue = 1 THEN 'Past Due Date'
        WHEN days_open > 90 THEN 'Open Too Long'
        WHEN label_status = 'blocked' THEN 'Blocked'
        WHEN assignee_username IS NULL THEN 'Unassigned'
        ELSE 'Other'
    END as risk_reason,
    web_url
FROM gitlab_hierarchy
WHERE state = 'opened'
    AND is_latest = 1
    AND (
        is_overdue = 1
        OR days_open > 90
        OR label_status = 'blocked'
        OR (assignee_username IS NULL AND label_priority IN ('critical', 'high'))
    )
ORDER BY
    CASE risk_level
        WHEN 'HIGH RISK' THEN 1
        WHEN 'MEDIUM RISK' THEN 2
        ELSE 3
    END,
    days_overdue DESC NULLS LAST;
```

### 3.2 Blocked Items Report

```sql
-- All blocked items with context
SELECT
    id,
    title,
    type,
    assignee_username,
    label_priority,
    days_open,
    label_status,
    parent_id,
    (SELECT title FROM gitlab_hierarchy gh2 WHERE gh2.id = gh1.parent_id AND gh2.is_latest = 1) as parent_title,
    web_url
FROM gitlab_hierarchy gh1
WHERE label_status = 'blocked'
    AND state = 'opened'
    AND is_latest = 1
ORDER BY
    CASE label_priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        ELSE 4
    END,
    days_open DESC;
```

### 3.3 Orphan Issues (Not in Epic Structure)

```sql
-- Issues not linked to any epic - potential scope gaps
SELECT
    project_path_with_namespace,
    title,
    state,
    assignee_username,
    milestone_title,
    label_priority,
    created_at,
    days_open,
    web_url
FROM gitlab_project_issues
WHERE has_epic = 0
    AND state = 'opened'
    AND is_latest = 1
ORDER BY
    CASE label_priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        ELSE 4
    END,
    created_at;
```

### 3.4 Critical Path Analysis

```sql
-- Identify critical epic dependencies
SELECT
    id,
    title,
    depth,
    child_count,
    descendant_count,
    completion_pct,
    label_priority,
    end_date,
    CASE
        WHEN end_date < DATE('now') THEN 'OVERDUE'
        WHEN end_date < DATE('now', '+14 days') THEN 'DUE SOON'
        ELSE 'ON TRACK'
    END as timeline_status,
    CASE
        WHEN descendant_count > 50 THEN 'LARGE'
        WHEN descendant_count > 20 THEN 'MEDIUM'
        ELSE 'SMALL'
    END as scope_size
FROM gitlab_hierarchy
WHERE type = 'epic'
    AND state = 'opened'
    AND is_latest = 1
    AND label_priority IN ('critical', 'high')
    AND depth <= 2  -- Focus on top-level epics
ORDER BY
    CASE
        WHEN end_date < DATE('now') THEN 1
        WHEN end_date < DATE('now', '+14 days') THEN 2
        ELSE 3
    END,
    descendant_count DESC;
```

---

## 4. Scope & Change Management

### 4.1 Scope Creep Detection

```sql
-- Track epics with growing scope (requires historical snapshots)
WITH current_scope AS (
    SELECT
        root_id,
        id,
        title,
        descendant_count as current_descendants,
        snapshot_date
    FROM gitlab_hierarchy
    WHERE type = 'epic'
        AND is_latest = 1
),
past_scope AS (
    SELECT
        root_id,
        id,
        descendant_count as past_descendants,
        snapshot_date
    FROM gitlab_hierarchy
    WHERE type = 'epic'
        AND snapshot_date = (
            SELECT MAX(snapshot_date)
            FROM gitlab_hierarchy
            WHERE snapshot_date < DATE('now', '-30 days')
        )
)
SELECT
    cs.id,
    cs.title,
    cs.current_descendants,
    COALESCE(ps.past_descendants, 0) as past_descendants,
    cs.current_descendants - COALESCE(ps.past_descendants, 0) as scope_change,
    ROUND(100.0 * (cs.current_descendants - COALESCE(ps.past_descendants, 0)) /
        NULLIF(ps.past_descendants, 1), 2) as pct_change,
    cs.snapshot_date as current_date,
    ps.snapshot_date as comparison_date
FROM current_scope cs
LEFT JOIN past_scope ps ON cs.id = ps.id
WHERE cs.current_descendants - COALESCE(ps.past_descendants, 0) > 0
ORDER BY scope_change DESC;
```

### 4.2 Recently Added Work Items

```sql
-- Issues added in last 30 days
SELECT
    parent_id,
    (SELECT title FROM gitlab_hierarchy gh2 WHERE gh2.id = gh1.parent_id AND gh2.is_latest = 1) as epic_title,
    title as issue_title,
    assignee_username,
    weight,
    DATE(created_at) as added_date,
    julianday('now') - julianday(created_at) as days_since_added,
    web_url
FROM gitlab_hierarchy gh1
WHERE type = 'issue'
    AND is_latest = 1
    AND created_at >= DATE('now', '-30 days')
ORDER BY created_at DESC;
```

### 4.3 Scope by Epic - Detailed Breakdown

```sql
-- Hierarchical scope breakdown
SELECT
    id,
    SUBSTR('                              ', 1, depth * 2) || title as indented_title,
    type,
    depth,
    child_count,
    descendant_count,
    SUM(CASE WHEN type = 'issue' THEN COALESCE(weight, 0) ELSE 0 END)
        OVER (PARTITION BY root_id) as total_root_points,
    state,
    completion_pct
FROM gitlab_hierarchy
WHERE root_id = 'epic:123#10'  -- Replace with your root epic
    AND is_latest = 1
ORDER BY hierarchy_path;
```

### 4.4 Change Request Tracking

```sql
-- Issues labeled as change requests
SELECT
    id,
    title,
    type,
    parent_id,
    label_change_type,  -- Assumes label like "change-type:scope-addition"
    assignee_username,
    state,
    created_at,
    closed_at,
    CASE WHEN closed_at IS NOT NULL THEN days_to_close END as days_to_approve,
    web_url
FROM gitlab_hierarchy
WHERE label_type = 'change-request'  -- Custom label
    AND is_latest = 1
ORDER BY created_at DESC;
```

---

## 5. Resource Allocation & Capacity

### 5.1 Team Workload Distribution

```sql
-- Current workload by team member
SELECT
    assignee_username,
    label_team,
    COUNT(*) as assigned_issues,
    SUM(COALESCE(weight, 0)) as total_story_points,
    SUM(CASE WHEN label_priority = 'critical' THEN 1 ELSE 0 END) as critical_items,
    SUM(CASE WHEN label_priority = 'high' THEN 1 ELSE 0 END) as high_priority_items,
    SUM(CASE WHEN is_overdue = 1 THEN 1 ELSE 0 END) as overdue_items,
    ROUND(AVG(days_open), 1) as avg_age_days
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND state = 'opened'
    AND is_latest = 1
    AND assignee_username IS NOT NULL
GROUP BY assignee_username, label_team
ORDER BY total_story_points DESC;
```

### 5.2 Capacity vs. Demand Analysis

```sql
-- Compare committed work vs capacity by team
WITH team_work AS (
    SELECT
        label_team,
        COUNT(DISTINCT assignee_username) as team_members,
        SUM(COALESCE(weight, 0)) as committed_points,
        COUNT(*) as committed_issues
    FROM gitlab_hierarchy
    WHERE type = 'issue'
        AND state = 'opened'
        AND is_latest = 1
        AND milestone_title = 'Sprint 23'  -- Current milestone
    GROUP BY label_team
)
SELECT
    label_team,
    team_members,
    committed_points,
    committed_issues,
    ROUND(1.0 * committed_points / NULLIF(team_members, 0), 1) as points_per_person,
    CASE
        WHEN committed_points / NULLIF(team_members, 0) > 40 THEN 'OVER CAPACITY'
        WHEN committed_points / NULLIF(team_members, 0) > 30 THEN 'AT CAPACITY'
        WHEN committed_points / NULLIF(team_members, 0) > 20 THEN 'UNDER CAPACITY'
        ELSE 'SIGNIFICANTLY UNDER'
    END as capacity_status
FROM team_work
ORDER BY points_per_person DESC;
```

### 5.3 Unassigned Work

```sql
-- Critical/high priority work without owners
SELECT
    id,
    title,
    type,
    label_priority,
    label_team,
    milestone_title,
    weight,
    due_date,
    days_open,
    web_url
FROM gitlab_hierarchy
WHERE assignee_username IS NULL
    AND state = 'opened'
    AND is_latest = 1
    AND label_priority IN ('critical', 'high')
ORDER BY
    CASE label_priority WHEN 'critical' THEN 1 ELSE 2 END,
    due_date NULLS LAST,
    days_open DESC;
```

### 5.4 Resource Allocation by Initiative

```sql
-- Team allocation across strategic initiatives
SELECT
    (SELECT title FROM gitlab_hierarchy gh2 WHERE gh2.id = gh1.root_id AND gh2.is_latest = 1) as initiative,
    label_team as team,
    COUNT(DISTINCT assignee_username) as team_members_allocated,
    COUNT(*) as issue_count,
    SUM(COALESCE(weight, 0)) as story_points,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct_of_total_work
FROM gitlab_hierarchy gh1
WHERE type = 'issue'
    AND state = 'opened'
    AND is_latest = 1
    AND assignee_username IS NOT NULL
GROUP BY root_id, label_team
ORDER BY initiative, story_points DESC;
```

---

## 6. Compliance & Audit

### 6.1 Audit Trail - Recent Changes

```sql
-- Track changes over snapshots (requires historical data)
SELECT
    id,
    title,
    type,
    snapshot_date,
    state,
    assignee_username,
    milestone_title,
    LAG(state) OVER (PARTITION BY id ORDER BY snapshot_date) as previous_state,
    LAG(assignee_username) OVER (PARTITION BY id ORDER BY snapshot_date) as previous_assignee,
    CASE
        WHEN state != LAG(state) OVER (PARTITION BY id ORDER BY snapshot_date) THEN 'State Changed'
        WHEN assignee_username != LAG(assignee_username) OVER (PARTITION BY id ORDER BY snapshot_date) THEN 'Reassigned'
        ELSE 'No Change'
    END as change_type
FROM gitlab_hierarchy
WHERE id = 'issue:456#123'  -- Specific item
ORDER BY snapshot_date DESC;
```

### 6.2 Compliance Coverage Report

```sql
-- Items tagged with compliance labels
SELECT
    label_compliance,  -- e.g., "compliance:sox", "compliance:gdpr"
    label_business_area,
    COUNT(*) as total_items,
    SUM(CASE WHEN state = 'closed' THEN 1 ELSE 0 END) as completed_items,
    SUM(CASE WHEN state = 'opened' THEN 1 ELSE 0 END) as open_items,
    SUM(CASE WHEN is_overdue = 1 THEN 1 ELSE 0 END) as overdue_items,
    ROUND(100.0 * SUM(CASE WHEN state = 'closed' THEN 1 ELSE 0 END) / COUNT(*), 2) as completion_pct
FROM gitlab_hierarchy
WHERE label_compliance IS NOT NULL
    AND is_latest = 1
GROUP BY label_compliance, label_business_area
ORDER BY label_compliance, label_business_area;
```

### 6.3 SLA Compliance Tracking

```sql
-- Issues exceeding SLA thresholds
SELECT
    id,
    title,
    label_priority,
    label_severity,
    state,
    created_at,
    closed_at,
    days_open,
    days_to_close,
    CASE label_severity
        WHEN 'critical' THEN 1  -- 1 day SLA
        WHEN 'high' THEN 3      -- 3 day SLA
        WHEN 'medium' THEN 7    -- 7 day SLA
        ELSE 14                 -- 14 day SLA
    END as sla_days,
    CASE
        WHEN state = 'opened' AND days_open > (
            CASE label_severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 7
                ELSE 14
            END
        ) THEN 'SLA BREACH'
        WHEN state = 'closed' AND days_to_close > (
            CASE label_severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 7
                ELSE 14
            END
        ) THEN 'SLA BREACHED (CLOSED)'
        ELSE 'WITHIN SLA'
    END as sla_status,
    web_url
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND is_latest = 1
    AND label_severity IS NOT NULL
ORDER BY
    CASE sla_status WHEN 'SLA BREACH' THEN 1 ELSE 2 END,
    days_open DESC;
```

### 6.4 Documentation Coverage

```sql
-- Check for documentation on epics
SELECT
    id,
    title,
    depth,
    child_count,
    descendant_count,
    CASE
        WHEN LENGTH(description) > 500 THEN 'Well Documented'
        WHEN LENGTH(description) > 100 THEN 'Partially Documented'
        WHEN LENGTH(description) > 0 THEN 'Minimal Documentation'
        ELSE 'No Documentation'
    END as documentation_status,
    LENGTH(description) as description_length,
    web_url
FROM gitlab_hierarchy
WHERE type = 'epic'
    AND is_latest = 1
    AND depth <= 2  -- Focus on strategic epics
ORDER BY
    CASE
        WHEN LENGTH(description) = 0 THEN 1
        WHEN LENGTH(description) <= 100 THEN 2
        WHEN LENGTH(description) <= 500 THEN 3
        ELSE 4
    END,
    descendant_count DESC;
```

---

## 7. Forecasting & Estimation

### 7.1 Velocity-Based Forecast

```sql
-- Calculate average velocity and forecast completion
WITH velocity_data AS (
    SELECT
        AVG(weekly_points) as avg_velocity
    FROM (
        SELECT
            strftime('%Y-%W', closed_at) as week,
            SUM(COALESCE(weight, 0)) as weekly_points
        FROM gitlab_hierarchy
        WHERE type = 'issue'
            AND state = 'closed'
            AND closed_at >= DATE('now', '-90 days')
            AND label_team = 'backend'  -- Filter by team
        GROUP BY week
    )
),
remaining_work AS (
    SELECT
        SUM(COALESCE(weight, 0)) as remaining_points,
        COUNT(*) as remaining_issues
    FROM gitlab_hierarchy
    WHERE type = 'issue'
        AND state = 'opened'
        AND is_latest = 1
        AND root_id = 'epic:123#10'  -- Specific initiative
)
SELECT
    rw.remaining_points,
    rw.remaining_issues,
    vd.avg_velocity,
    ROUND(rw.remaining_points / NULLIF(vd.avg_velocity, 0), 1) as estimated_weeks,
    DATE('now', '+' || CAST(ROUND(rw.remaining_points / NULLIF(vd.avg_velocity, 0)) AS INTEGER) || ' weeks') as forecast_completion_date
FROM remaining_work rw, velocity_data vd;
```

### 7.2 Estimation Accuracy

```sql
-- Compare estimated vs actual effort (using time tracking)
SELECT
    label_team,
    COUNT(*) as completed_issues,
    SUM(time_estimate) / 3600.0 as total_estimated_hours,
    SUM(time_spent) / 3600.0 as total_actual_hours,
    ROUND((SUM(time_spent) - SUM(time_estimate)) / 3600.0, 2) as variance_hours,
    ROUND(100.0 * SUM(time_spent) / NULLIF(SUM(time_estimate), 0) - 100, 2) as variance_pct,
    CASE
        WHEN 100.0 * SUM(time_spent) / NULLIF(SUM(time_estimate), 0) - 100 > 50 THEN 'Significant Underestimation'
        WHEN 100.0 * SUM(time_spent) / NULLIF(SUM(time_estimate), 0) - 100 > 20 THEN 'Moderate Underestimation'
        WHEN 100.0 * SUM(time_spent) / NULLIF(SUM(time_estimate), 0) - 100 < -20 THEN 'Overestimation'
        ELSE 'Accurate'
    END as estimation_quality
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND state = 'closed'
    AND is_latest = 1
    AND time_estimate > 0
    AND closed_at >= DATE('now', '-90 days')
GROUP BY label_team
ORDER BY variance_pct DESC;
```

### 7.3 Complexity Distribution

```sql
-- Understand distribution of work complexity
SELECT
    CASE
        WHEN weight IS NULL THEN 'Unestimated'
        WHEN weight <= 1 THEN 'XS (1 point)'
        WHEN weight <= 3 THEN 'S (2-3 points)'
        WHEN weight <= 5 THEN 'M (4-5 points)'
        WHEN weight <= 8 THEN 'L (6-8 points)'
        ELSE 'XL (9+ points)'
    END as size_category,
    COUNT(*) as issue_count,
    SUM(COALESCE(weight, 0)) as total_points,
    ROUND(AVG(days_to_close), 1) as avg_cycle_time,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct_of_total
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND is_latest = 1
    AND state = 'closed'
    AND closed_at >= DATE('now', '-90 days')
GROUP BY size_category
ORDER BY
    CASE size_category
        WHEN 'XS (1 point)' THEN 1
        WHEN 'S (2-3 points)' THEN 2
        WHEN 'M (4-5 points)' THEN 3
        WHEN 'L (6-8 points)' THEN 4
        WHEN 'XL (9+ points)' THEN 5
        ELSE 6
    END;
```

### 7.4 Monte Carlo Simulation Input Data

```sql
-- Get cycle time distribution for Monte Carlo forecasting
SELECT
    percentile,
    days_to_close as cycle_time_days
FROM (
    SELECT
        days_to_close,
        NTILE(100) OVER (ORDER BY days_to_close) as percentile
    FROM gitlab_hierarchy
    WHERE type = 'issue'
        AND state = 'closed'
        AND days_to_close IS NOT NULL
        AND closed_at >= DATE('now', '-90 days')
        AND label_team = 'backend'
)
WHERE percentile IN (10, 25, 50, 75, 90, 95)
ORDER BY percentile;
```

---

## 8. Team Performance & Metrics

### 8.1 Team Throughput

```sql
-- Issues closed per week by team
SELECT
    strftime('%Y-W%W', closed_at) as week,
    label_team,
    COUNT(*) as issues_closed,
    SUM(COALESCE(weight, 0)) as points_delivered,
    ROUND(AVG(days_to_close), 1) as avg_cycle_time,
    COUNT(DISTINCT assignee_username) as active_contributors
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND state = 'closed'
    AND closed_at >= DATE('now', '-90 days')
    AND is_latest = 1
GROUP BY week, label_team
ORDER BY week DESC, label_team;
```

### 8.2 Cycle Time Analysis

```sql
-- Detailed cycle time metrics by team
SELECT
    label_team,
    label_type,
    COUNT(*) as completed_issues,
    ROUND(AVG(days_to_close), 1) as avg_cycle_time,
    ROUND(MIN(days_to_close), 1) as min_cycle_time,
    ROUND(MAX(days_to_close), 1) as max_cycle_time,
    (SELECT days_to_close
     FROM gitlab_hierarchy gh2
     WHERE gh2.type = 'issue'
        AND gh2.state = 'closed'
        AND gh2.label_team = gh1.label_team
        AND gh2.label_type = gh1.label_type
        AND gh2.days_to_close IS NOT NULL
        AND gh2.is_latest = 1
     ORDER BY days_to_close
     LIMIT 1 OFFSET (COUNT(*) / 2)
    ) as median_cycle_time
FROM gitlab_hierarchy gh1
WHERE type = 'issue'
    AND state = 'closed'
    AND days_to_close IS NOT NULL
    AND is_latest = 1
    AND closed_at >= DATE('now', '-90 days')
GROUP BY label_team, label_type
ORDER BY label_team, avg_cycle_time DESC;
```

### 8.3 Quality Metrics - Defect Rate

```sql
-- Bug ratio and resolution time
SELECT
    label_team,
    COUNT(*) as total_issues,
    SUM(CASE WHEN label_type = 'bug' THEN 1 ELSE 0 END) as bug_count,
    SUM(CASE WHEN label_type = 'feature' THEN 1 ELSE 0 END) as feature_count,
    ROUND(100.0 * SUM(CASE WHEN label_type = 'bug' THEN 1 ELSE 0 END) / COUNT(*), 2) as bug_percentage,
    ROUND(AVG(CASE WHEN label_type = 'bug' THEN days_to_close END), 1) as avg_bug_resolution_days,
    ROUND(AVG(CASE WHEN label_type = 'feature' THEN days_to_close END), 1) as avg_feature_completion_days
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND state = 'closed'
    AND is_latest = 1
    AND closed_at >= DATE('now', '-90 days')
GROUP BY label_team
ORDER BY bug_percentage DESC;
```

### 8.4 Individual Contributor Performance

```sql
-- Detailed individual metrics
SELECT
    assignee_username,
    label_team,
    COUNT(*) as completed_issues,
    SUM(COALESCE(weight, 0)) as points_completed,
    ROUND(AVG(days_to_close), 1) as avg_cycle_time,
    SUM(CASE WHEN label_type = 'bug' THEN 1 ELSE 0 END) as bugs_fixed,
    SUM(CASE WHEN label_type = 'feature' THEN 1 ELSE 0 END) as features_delivered,
    ROUND(AVG(CASE WHEN label_priority = 'critical' THEN days_to_close END), 1) as avg_critical_resolution_time
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND state = 'closed'
    AND is_latest = 1
    AND assignee_username IS NOT NULL
    AND closed_at >= DATE('now', '-90 days')
GROUP BY assignee_username, label_team
ORDER BY points_completed DESC;
```

### 8.5 Team Efficiency - WIP Analysis

```sql
-- Work In Progress by team member
SELECT
    assignee_username,
    label_team,
    COUNT(*) as wip_count,
    SUM(COALESCE(weight, 0)) as wip_points,
    SUM(CASE WHEN label_status = 'in-progress' THEN 1 ELSE 0 END) as actively_working,
    SUM(CASE WHEN label_status = 'blocked' THEN 1 ELSE 0 END) as blocked_count,
    ROUND(AVG(days_open), 1) as avg_age_days,
    MAX(days_open) as oldest_item_age,
    CASE
        WHEN COUNT(*) > 5 THEN 'TOO MUCH WIP'
        WHEN COUNT(*) > 3 THEN 'HIGH WIP'
        WHEN COUNT(*) <= 2 THEN 'HEALTHY WIP'
        ELSE 'MODERATE WIP'
    END as wip_status
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND state = 'opened'
    AND is_latest = 1
    AND assignee_username IS NOT NULL
GROUP BY assignee_username, label_team
ORDER BY wip_count DESC;
```

### 8.6 Team Collaboration Score

```sql
-- Issues with multiple assignees or cross-team collaboration
SELECT
    label_team as primary_team,
    label_collaboration as collaborating_with,  -- Custom label for cross-team work
    COUNT(*) as collaborative_issues,
    SUM(COALESCE(weight, 0)) as collaborative_points,
    ROUND(AVG(days_to_close), 1) as avg_completion_time
FROM gitlab_hierarchy
WHERE type = 'issue'
    AND is_latest = 1
    AND label_collaboration IS NOT NULL
    AND closed_at >= DATE('now', '-90 days')
GROUP BY label_team, label_collaboration
ORDER BY collaborative_issues DESC;
```

---

## Best Practices for Epic & Issue Organization

### Epic Hierarchy Structure

```
Root Epic (Depth 0)
└── Strategic Initiative / Program (Depth 1)
    └── Feature / Deliverable (Depth 2)
        └── Sub-Feature / Component (Depth 3)
            └── Issues (Leaf nodes)
```

### Guidelines for Epics

1. **Depth 0-1 (Portfolio Level)**
   - Strategic initiatives aligned with business objectives
   - Duration: Quarter to year
   - Owner: Executive sponsor or product lead
   - Must have: Start/end dates, business area, priority, theme

2. **Depth 2-3 (Product/Feature Level)**
   - Deliverables and capabilities
   - Duration: Month to quarter
   - Owner: Product manager or tech lead
   - Must have: Clear acceptance criteria, dependencies

3. **Issues (Execution Level)**
   - Atomic work items
   - Duration: Days to 2 weeks
   - Owner: Individual contributor
   - Must have: Estimate, assignee, milestone, acceptance criteria

### Epic Creation Checklist

- [ ] Clear, outcome-focused title
- [ ] Detailed description with business context
- [ ] Start and end dates
- [ ] Assigned to epic owner
- [ ] Priority set
- [ ] Labels applied (theme, business area, quarter, etc.)
- [ ] Parent epic linked (if applicable)
- [ ] Dependencies documented

### Issue Creation Checklist

- [ ] Linked to parent epic
- [ ] Story points/weight estimated
- [ ] Assigned to team member
- [ ] Milestone set
- [ ] Priority and type labels applied
- [ ] Acceptance criteria defined
- [ ] Technical approach outlined (for complex issues)

---

## Label Management Strategy

### Recommended Label Taxonomy

#### 1. Priority Labels (Mutually Exclusive)
```
priority:critical   - Production outage, blocking all work
priority:high       - Important, blocking significant work
priority:medium     - Important but not blocking
priority:low        - Nice to have, can be deferred
```

#### 2. Type Labels (Mutually Exclusive)
```
type:feature        - New functionality
type:enhancement    - Improvement to existing feature
type:bug            - Defect fix
type:technical-debt - Refactoring, cleanup
type:documentation  - Documentation work
type:research       - Spike, investigation
```

#### 3. Status Labels
```
status:backlog      - Not yet started
status:ready        - Ready to be picked up
status:in-progress  - Actively being worked on
status:blocked      - Waiting on dependency
status:review       - In code review
status:testing      - In QA/testing
```

#### 4. Team Labels
```
team:backend        - Backend team
team:frontend       - Frontend team
team:data           - Data team
team:infrastructure - Infrastructure/DevOps
team:design         - Design team
team:qa             - QA team
```

#### 5. Component Labels
```
component:api       - API layer
component:database  - Database
component:ui        - User interface
component:auth      - Authentication
component:integration - Third-party integration
```

#### 6. Business Labels
```
business-area:sales     - Sales domain
business-area:marketing - Marketing domain
business-area:finance   - Finance domain
business-area:operations - Operations domain
```

#### 7. Theme/Strategic Labels
```
theme:customer-experience  - CX improvement
theme:performance         - Performance optimization
theme:security            - Security enhancement
theme:scalability         - Scalability work
```

#### 8. Quarter/Release Labels
```
quarter:2025-q1
quarter:2025-q2
release:v2.5
release:v3.0
```

#### 9. Compliance Labels (if applicable)
```
compliance:sox      - Sarbanes-Oxley
compliance:gdpr     - GDPR requirement
compliance:hipaa    - HIPAA requirement
compliance:audit    - Audit-related
```

#### 10. Special Flags
```
flag:customer-requested  - Direct customer request
flag:revenue-impact      - Impacts revenue
flag:breaking-change     - Breaking API change
flag:needs-documentation - Requires doc update
```

### Label Naming Conventions

1. **Use category prefixes**: `category:value` (e.g., `priority:high`, `team:backend`)
2. **Use kebab-case**: `multi-word-labels` not `Multi Word Labels`
3. **Be consistent**: Decide on singular vs plural and stick with it
4. **Keep it hierarchical**: Use parent:child structure where appropriate
5. **Avoid redundancy**: Don't create `priority-high` and `high-priority`

### Label Color Coding

```
Priority: Red shades (critical=dark red, high=red, medium=orange, low=yellow)
Type: Blue shades (feature=blue, bug=red, enhancement=cyan)
Status: Green/yellow shades (done=green, in-progress=yellow, blocked=red)
Team: Purple shades (different shade per team)
```

### Label Governance

1. **Centralized Label Management**
   - Create labels at group level (inherited by all projects)
   - Restrict label creation to maintainers
   - Regular label audits to remove unused labels

2. **Label Templates**
   - Create issue templates that pre-populate required labels
   - Use GitLab's quick actions to set labels

3. **Validation Rules**
   - Every issue MUST have: priority, type, team
   - Every epic MUST have: priority, theme, business-area, quarter
   - Use CI/CD pipelines to validate label presence

4. **Documentation**
   - Maintain a label glossary in project wiki
   - Include examples of when to use each label
   - Train team on label usage

### Example: Well-Labeled Issue

```
Title: Add user export functionality to admin dashboard

Labels:
  - priority:high
  - type:feature
  - team:backend
  - component:api
  - component:database
  - business-area:operations
  - theme:customer-experience
  - quarter:2025-q2
  - flag:customer-requested

Epic: Admin Dashboard Enhancements (#345)
Milestone: Sprint 23
Weight: 5
Assignee: @john.doe
```

### Example: Well-Labeled Epic

```
Title: Modernize Authentication System

Labels:
  - priority:critical
  - theme:security
  - business-area:platform
  - quarter:2025-q2
  - compliance:sox
  - flag:breaking-change

Parent Epic: Security & Compliance Initiative (#100)
Start Date: 2025-04-01
End Date: 2025-06-30
Owner: @security-lead
```

---

## Additional Tips

### For Better Reporting

1. **Use consistent date formats** in custom fields
2. **Estimate everything** - even rough estimates enable forecasting
3. **Update regularly** - stale data leads to poor decisions
4. **Link related items** - enables dependency analysis
5. **Use milestones** - critical for sprint/release tracking
6. **Track time** - enables estimation accuracy improvement
7. **Add descriptions** - context is crucial for understanding
8. **Use comments** - document decisions and changes
9. **Close completed items promptly** - keeps metrics accurate
10. **Archive obsolete work** - reduces noise

### Data Quality Checks

Run these queries periodically to ensure data quality:

```sql
-- Issues without estimates
SELECT COUNT(*) as unestimated_issues
FROM gitlab_hierarchy
WHERE type = 'issue' AND weight IS NULL AND state = 'opened' AND is_latest = 1;

-- Issues without assignees
SELECT COUNT(*) as unassigned_issues
FROM gitlab_hierarchy
WHERE type = 'issue' AND assignee_username IS NULL AND state = 'opened' AND is_latest = 1;

-- Issues without priority
SELECT COUNT(*) as no_priority_issues
FROM gitlab_hierarchy
WHERE type = 'issue' AND label_priority IS NULL AND state = 'opened' AND is_latest = 1;

-- Epics without dates
SELECT COUNT(*) as epics_without_dates
FROM gitlab_hierarchy
WHERE type = 'epic' AND (start_date IS NULL OR end_date IS NULL) AND state = 'opened' AND is_latest = 1;
```

---

## Automation Recommendations

### GitLab CI/CD Integration

Create validation jobs that run on issue/epic creation:

```yaml
# .gitlab-ci.yml
validate-labels:
  script:
    - python scripts/validate_labels.py
  rules:
    - if: '$CI_MERGE_REQUEST_LABELS !~ /priority:/'
      when: manual
```

### Scheduled Reports

Use cron jobs to run key queries and email results:

```bash
# Daily risk report
0 9 * * * cd /path/to/TheMatrix && neo extract --group-ids "123,456" && sqlite3 hierarchy.db < reports/daily_risks.sql | mail -s "Daily Risk Report" team@company.com
```

### Dashboard Integration

Export query results to BI tools:
- Tableau
- Power BI
- Metabase
- Grafana (with SQLite plugin)

---

**Last Updated**: 2025-12-19
**Version**: 1.0
**Status**: Ready for Production Use
