"""
GitLab Epic & Issue Hierarchy Extractor

A tool to extract GitLab epic hierarchies and store them in SQLite for reporting.
"""

__version__ = "1.0.0"
__author__ = "GitLab Hierarchy Tool"

from .extractor import HierarchyExtractor
from .database import Database
from .gitlab_client import GitLabClient

__all__ = [
    "HierarchyExtractor",
    "Database",
    "GitLabClient",
]
