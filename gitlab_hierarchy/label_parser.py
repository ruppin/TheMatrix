"""
Label parsing and normalization logic.
"""

import logging
import re
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class LabelParser:
    """Parse and normalize GitLab labels into structured columns."""

    def __init__(self, patterns: Optional[List[Dict]] = None):
        """
        Initialize label parser.

        Args:
            patterns: List of label pattern dictionaries with 'prefix' and 'column'
        """
        # Default patterns
        self.patterns = patterns or [
            {'prefix': 'priority', 'column': 'label_priority'},
            {'prefix': 'type', 'column': 'label_type'},
            {'prefix': 'status', 'column': 'label_status'},
            {'prefix': 'team', 'column': 'label_team'},
            {'prefix': 'component', 'column': 'label_component'},
        ]

        # Track custom label categories found
        self.custom_categories: Set[str] = set()

    def parse_labels(self, labels: List[str]) -> Dict[str, str]:
        """
        Parse list of labels into normalized columns.

        Args:
            labels: List of label strings

        Returns:
            Dictionary with label column values
        """
        result = {
            'labels_raw': labels,  # Keep original
        }

        # Initialize all known columns to None
        for pattern in self.patterns:
            result[pattern['column']] = None

        # Parse each label
        for label in labels:
            # Try to match against known patterns
            matched = False

            for pattern in self.patterns:
                prefix = pattern['prefix']
                column = pattern['column']

                # Check if label matches pattern "prefix:value" or "prefix-value"
                match = re.match(f"^{prefix}[:-](.+)$", label, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Store value (first match wins)
                    if not result[column]:
                        result[column] = value
                    matched = True
                    break

            # If no match, check if it's a custom category
            if not matched:
                self._extract_custom_category(label, result)

        return result

    def _extract_custom_category(self, label: str, result: Dict):
        """
        Extract custom label categories not matching standard patterns.

        Args:
            label: Label string
            result: Result dictionary to update
        """
        # Check if label has "category:value" or "category-value" format
        match = re.match(r'^([a-zA-Z0-9_]+)[:-](.+)$', label)

        if match:
            category = match.group(1).lower()
            value = match.group(2).strip()

            # Track new categories
            if category not in self.custom_categories:
                self.custom_categories.add(category)
                logger.debug(f"Discovered custom label category: {category}")

            # Store in custom columns (up to 3)
            custom_columns = ['label_custom_1', 'label_custom_2', 'label_custom_3']

            for col in custom_columns:
                if col not in result or result[col] is None:
                    result[col] = f"{category}:{value}"
                    break

    def parse_items(self, items: List[Dict]) -> List[Dict]:
        """
        Parse labels for a list of items.

        Args:
            items: List of item dictionaries

        Returns:
            List of items with parsed labels
        """
        logger.info(f"Parsing labels for {len(items)} items")

        for item in items:
            labels = item.get('labels_raw', [])
            if labels:
                parsed = self.parse_labels(labels)
                item.update(parsed)

        if self.custom_categories:
            logger.info(f"Discovered {len(self.custom_categories)} custom label categories: {sorted(self.custom_categories)}")

        return items

    def get_discovered_categories(self) -> Set[str]:
        """
        Get all custom label categories discovered during parsing.

        Returns:
            Set of category names
        """
        return self.custom_categories

    def add_pattern(self, prefix: str, column: str):
        """
        Add a new label pattern.

        Args:
            prefix: Label prefix to match
            column: Column name to store value
        """
        self.patterns.append({'prefix': prefix, 'column': column})
        logger.debug(f"Added label pattern: {prefix} -> {column}")
