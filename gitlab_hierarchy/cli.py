"""
Command-line interface for GitLab hierarchy extractor.
"""

import os
import sys
import logging
from datetime import date
import click

from .extractor import HierarchyExtractor
from .database import Database


# Setup logging
def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """GitLab Epic & Issue Hierarchy Extractor to SQLite."""
    pass


@cli.command(name='extract')
@click.option('--group-ids', required=True, help='Comma-separated list of group IDs to fetch epics from')
@click.option('--root-group-id', type=int, required=True, help='Group ID containing the root epic')
@click.option('--epic-iid', type=int, required=True, help='Epic IID of the root epic')
@click.option('--db', 'db_path', default='hierarchy.db', help='SQLite database path')
@click.option('--gitlab-url', default='https://gitlab.com', help='GitLab instance URL')
@click.option('--token', default=lambda: os.getenv('GITLAB_TOKEN'), help='GitLab personal access token')
@click.option('--snapshot-date', type=click.DateTime(formats=['%Y-%m-%d']), help='Snapshot date (default: today)')
@click.option('--include-closed/--no-include-closed', default=True, help='Include closed items')
@click.option('--max-depth', type=int, default=20, help='Maximum hierarchy depth')
@click.option('--verbose', is_flag=True, help='Verbose output')
def extract_from_groups(group_ids, root_group_id, epic_iid, db_path, gitlab_url, token, snapshot_date, include_closed, max_depth, verbose):
    """
    Extract epic hierarchy from groups using in-memory method.

    This command fetches all epics from the specified groups upfront and builds
    the hierarchy in-memory using parent_epic_id relationships. This is more
    reliable than relying on GitLab's parent_id API filter.

    Example:
        neo extract --group-ids "123,456,789" --root-group-id 123 --epic-iid 1
    """
    setup_logging(verbose)

    if not token:
        click.echo("Error: GitLab token required. Set GITLAB_TOKEN environment variable or use --token", err=True)
        sys.exit(1)

    # Parse group IDs
    try:
        group_id_list = [int(gid.strip()) for gid in group_ids.split(',')]
    except ValueError:
        click.echo("Error: Invalid group IDs format. Use comma-separated integers (e.g., '123,456,789')", err=True)
        sys.exit(1)

    # Ensure root_group_id is in the list
    if root_group_id not in group_id_list:
        click.echo(f"Warning: root-group-id {root_group_id} not in group-ids list. Adding it automatically.")
        group_id_list.append(root_group_id)

    # Convert snapshot_date if provided
    if snapshot_date:
        snapshot_date = snapshot_date.date()

    try:
        extractor = HierarchyExtractor(
            gitlab_url=gitlab_url,
            token=token,
            db_path=db_path,
            rate_limit_delay=0.5
        )

        result = extractor.extract_from_groups(
            group_ids=group_id_list,
            root_group_id=root_group_id,
            root_epic_iid=epic_iid,
            snapshot_date=snapshot_date,
            include_closed=include_closed,
            max_depth=max_depth,
            verbose=verbose
        )

        extractor.close()

        if result['success']:
            click.echo("\n✓ Extraction completed successfully!")
            sys.exit(0)
        else:
            click.echo("\n✗ Extraction failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"\n✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command(name='extract-issues')
@click.option('--group-ids', required=True, help='Comma-separated list of group IDs to fetch issues from')
@click.option('--db', 'db_path', default='hierarchy.db', help='SQLite database path')
@click.option('--gitlab-url', default='https://gitlab.com', help='GitLab instance URL')
@click.option('--token', default=lambda: os.getenv('GITLAB_TOKEN'), help='GitLab personal access token')
@click.option('--snapshot-date', type=click.DateTime(formats=['%Y-%m-%d']), help='Snapshot date (default: today)')
@click.option('--include-closed/--no-include-closed', default=True, help='Include closed items')
@click.option('--verbose', is_flag=True, help='Verbose output')
def extract_issues_from_groups(group_ids, db_path, gitlab_url, token, snapshot_date, include_closed, verbose):
    """
    Extract ALL issues from projects in groups (includes orphan issues).

    This command fetches ALL issues from all projects in the specified groups,
    regardless of whether they are linked to epics. Issues are stored in the
    gitlab_project_issues table with epic linkage information included.

    Use this to:
    - Get a complete inventory of all issues in your groups
    - Identify issues that are not linked to any epic (orphans)
    - Analyze issues independently from the epic hierarchy

    Example:
        neo extract-issues --group-ids "123,456,789"
    """
    setup_logging(verbose)

    if not token:
        click.echo("Error: GitLab token required. Set GITLAB_TOKEN environment variable or use --token", err=True)
        sys.exit(1)

    # Parse group IDs
    try:
        group_id_list = [int(gid.strip()) for gid in group_ids.split(',')]
    except ValueError:
        click.echo("Error: Invalid group IDs format. Use comma-separated integers (e.g., '123,456,789')", err=True)
        sys.exit(1)

    # Convert snapshot_date if provided
    if snapshot_date:
        snapshot_date = snapshot_date.date()

    try:
        extractor = HierarchyExtractor(
            gitlab_url=gitlab_url,
            token=token,
            db_path=db_path,
            rate_limit_delay=0.5
        )

        result = extractor.extract_issues_from_groups(
            group_ids=group_id_list,
            snapshot_date=snapshot_date,
            include_closed=include_closed,
            verbose=verbose
        )

        extractor.close()

        if result['success']:
            click.echo("\n✓ Extraction completed successfully!")
            click.echo(f"  Total issues: {result['total_issues']}")
            click.echo(f"  Epic-linked: {result['epic_linked_count']}")
            click.echo(f"  Orphan issues: {result['orphan_count']}")
            sys.exit(0)
        else:
            click.echo("\n✗ Extraction failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"\n✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--db', 'db_path', default='hierarchy.db', help='SQLite database path')
@click.option('--root-id', help='Root epic ID to show stats for (optional)')
def stats(db_path, root_id):
    """Show database statistics."""
    setup_logging()

    try:
        db = Database(db_path)
        stats = db.get_stats(root_id=root_id)

        click.echo("\n" + "=" * 80)
        click.echo("DATABASE STATISTICS")
        click.echo("=" * 80)

        if root_id:
            click.echo(f"Root ID: {root_id}")
            click.echo("")

        click.echo(f"Total Items: {stats.get('total_items', 0)}")
        click.echo(f"  Epics: {stats.get('epic_count', 0)}")
        click.echo(f"  Issues: {stats.get('issue_count', 0)}")
        click.echo("")
        click.echo(f"State:")
        click.echo(f"  Open: {stats.get('open_count', 0)}")
        click.echo(f"  Closed: {stats.get('closed_count', 0)}")
        click.echo("")
        click.echo(f"Hierarchy:")
        click.echo(f"  Max Depth: {stats.get('max_depth', 0)} levels")
        click.echo(f"  Avg Depth: {stats.get('avg_depth', 0):.1f} levels")
        click.echo(f"  Leaf Nodes: {stats.get('leaf_count', 0)}")
        click.echo("")
        click.echo(f"Roots: {stats.get('root_count', 0)}")
        click.echo("")
        click.echo(f"Snapshots:")
        click.echo(f"  First: {stats.get('first_snapshot', 'N/A')}")
        click.echo(f"  Last: {stats.get('last_snapshot', 'N/A')}")
        click.echo("=" * 80)

        db.close()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--db', 'db_path', default='hierarchy.db', help='SQLite database path')
@click.option('--keep-days', type=int, default=90, help='Number of days to keep')
def cleanup(db_path, keep_days):
    """Clean up old snapshots."""
    setup_logging()

    try:
        db = Database(db_path)
        deleted = db.cleanup_old_snapshots(keep_days)

        click.echo(f"\n✓ Cleaned up {deleted} old snapshot(s)")
        click.echo(f"  Kept snapshots from last {keep_days} days")

        db.close()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--db', 'db_path', default='hierarchy.db', help='SQLite database path')
@click.option('--format', 'output_format', type=click.Choice(['csv', 'json']), default='csv', help='Export format')
@click.option('--output', default='export.csv', help='Output file path')
@click.option('--root-id', help='Root epic ID to export (optional)')
def export(db_path, output_format, output, root_id):
    """Export data to CSV or JSON."""
    setup_logging()

    try:
        import pandas as pd

        db = Database(db_path)

        # Build query
        if root_id:
            sql = "SELECT * FROM gitlab_hierarchy WHERE root_id = ? AND is_latest = 1"
            params = (root_id,)
        else:
            sql = "SELECT * FROM gitlab_hierarchy WHERE is_latest = 1"
            params = ()

        results = db.execute_query(sql, params)

        if not results:
            click.echo("No data to export", err=True)
            sys.exit(1)

        df = pd.DataFrame(results)

        if output_format == 'csv':
            df.to_csv(output, index=False)
            click.echo(f"\n✓ Exported {len(df)} rows to {output} (CSV)")
        else:
            df.to_json(output, orient='records', indent=2)
            click.echo(f"\n✓ Exported {len(df)} rows to {output} (JSON)")

        db.close()

    except ImportError:
        click.echo("Error: pandas required for export. Install with: pip install pandas", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--db', 'db_path', default='hierarchy.db', help='SQLite database path')
@click.option('--sql', required=True, help='SQL query to execute')
def query(db_path, sql):
    """Execute a custom SQL query."""
    setup_logging()

    try:
        import pandas as pd

        db = Database(db_path)
        results = db.execute_query(sql)

        if not results:
            click.echo("No results")
        else:
            df = pd.DataFrame(results)
            click.echo(f"\n{df.to_string()}")
            click.echo(f"\n({len(df)} rows)")

        db.close()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
