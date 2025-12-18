"""
Tests for label parsing functionality.
"""

import pytest
from gitlab_hierarchy.label_parser import LabelParser


def test_default_patterns():
    """Test parsing with default patterns."""
    parser = LabelParser()

    labels = [
        'priority:high',
        'type:bug',
        'status:in-progress',
        'team:backend',
        'component:api'
    ]

    result = parser.parse_labels(labels)

    assert result['label_priority'] == 'high'
    assert result['label_type'] == 'bug'
    assert result['label_status'] == 'in-progress'
    assert result['label_team'] == 'backend'
    assert result['label_component'] == 'api'


def test_custom_patterns():
    """Test parsing with custom patterns."""
    custom_patterns = {
        'severity': 'label_severity',
        'area': 'label_area',
    }

    parser = LabelParser(custom_patterns)

    labels = [
        'severity:critical',
        'area:authentication',
        'priority:high'
    ]

    result = parser.parse_labels(labels)

    assert result['label_severity'] == 'critical'
    assert result['label_area'] == 'authentication'
    assert result['label_priority'] == 'high'


def test_hyphen_separator():
    """Test parsing labels with hyphen separator."""
    parser = LabelParser()

    labels = [
        'priority-high',
        'type-feature'
    ]

    result = parser.parse_labels(labels)

    assert result['label_priority'] == 'high'
    assert result['label_type'] == 'feature'


def test_multiple_values_same_category():
    """Test handling multiple values for same category (should use first)."""
    parser = LabelParser()

    labels = [
        'priority:high',
        'priority:low'
    ]

    result = parser.parse_labels(labels)

    # Should use first occurrence
    assert result['label_priority'] == 'high'


def test_unknown_categories():
    """Test handling of unknown label categories."""
    parser = LabelParser()

    labels = [
        'priority:high',
        'unknown:value1',
        'another:value2',
        'third:value3',
        'fourth:value4'  # Should overflow beyond custom_3
    ]

    result = parser.parse_labels(labels)

    assert result['label_priority'] == 'high'
    assert result['label_custom_1'] == 'unknown:value1'
    assert result['label_custom_2'] == 'another:value2'
    assert result['label_custom_3'] == 'third:value3'
    # fourth should be ignored (only 3 custom slots)

    categories = parser.get_discovered_categories()
    assert 'unknown' in categories
    assert 'another' in categories


def test_labels_without_category():
    """Test handling labels that don't match pattern."""
    parser = LabelParser()

    labels = [
        'priority:high',
        'simple-label',
        'another-simple',
        'type:bug'
    ]

    result = parser.parse_labels(labels)

    assert result['label_priority'] == 'high'
    assert result['label_type'] == 'bug'
    # Simple labels without category prefix should be ignored or stored in custom


def test_empty_labels():
    """Test handling empty label list."""
    parser = LabelParser()

    result = parser.parse_labels([])

    # All label fields should be None
    assert result['label_priority'] is None
    assert result['label_type'] is None
    assert result['label_status'] is None


def test_parse_items_batch():
    """Test parsing labels for multiple items."""
    parser = LabelParser()

    items = [
        {
            'id': 'epic:1',
            'labels': ['priority:high', 'type:epic'],
            'title': 'Epic 1'
        },
        {
            'id': 'issue:1',
            'labels': ['priority:low', 'type:bug'],
            'title': 'Issue 1'
        }
    ]

    result = parser.parse_items(items)

    assert len(result) == 2
    assert result[0]['label_priority'] == 'high'
    assert result[0]['label_type'] == 'epic'
    assert result[1]['label_priority'] == 'low'
    assert result[1]['label_type'] == 'bug'
    # Original fields should be preserved
    assert result[0]['title'] == 'Epic 1'
    assert result[1]['title'] == 'Issue 1'


def test_add_pattern():
    """Test dynamically adding patterns."""
    parser = LabelParser()

    parser.add_pattern('env', 'label_environment')

    labels = ['env:production', 'priority:high']
    result = parser.parse_labels(labels)

    assert result['label_environment'] == 'production'
    assert result['label_priority'] == 'high'


def test_case_sensitivity():
    """Test case handling in labels."""
    parser = LabelParser()

    labels = [
        'Priority:High',
        'TYPE:BUG'
    ]

    result = parser.parse_labels(labels)

    # Pattern matching should be case-insensitive for prefix
    assert result['label_priority'] == 'High'
    assert result['label_type'] == 'BUG'


def test_special_characters_in_values():
    """Test labels with special characters in values."""
    parser = LabelParser()

    labels = [
        'team:back-end',
        'component:api/v2',
        'status:ready-for-review'
    ]

    result = parser.parse_labels(labels)

    assert result['label_team'] == 'back-end'
    assert result['label_component'] == 'api/v2'
    assert result['label_status'] == 'ready-for-review'
