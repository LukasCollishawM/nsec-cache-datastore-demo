"""
Unit tests for the ordering module.

Tests DNS name generation, in-gap name generation, and lexicographic ordering.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nsecchain.ordering import (
    node_name_for_index,
    in_gap_name,
    verification_in_gap_name,
    is_name_between,
    extract_index_from_name,
    parse_node_name,
    get_next_node_index
)


class TestNodeNameForIndex:
    """Tests for node_name_for_index function."""
    
    def test_basic_name_generation(self):
        """Test basic node name generation."""
        result = node_name_for_index(0, 'nbswy3dp', 'zone.test')
        assert result == 'n0000.nbswy3dp.zone.test.'
    
    def test_index_formatting(self):
        """Test index is zero-padded to 4 digits."""
        result = node_name_for_index(1, 'payload', 'zone.test')
        assert result.startswith('n0001.')
        
        result = node_name_for_index(99, 'payload', 'zone.test')
        assert result.startswith('n0099.')
        
        result = node_name_for_index(999, 'payload', 'zone.test')
        assert result.startswith('n0999.')
    
    def test_relative_name(self):
        """Test relative name (no trailing dot)."""
        result = node_name_for_index(0, 'payload', 'zone.test', absolute=False)
        assert not result.endswith('.')
        assert result == 'n0000.payload.zone.test'
    
    def test_zone_normalization(self):
        """Test zone name is normalized (trailing dot removed from input)."""
        result1 = node_name_for_index(0, 'payload', 'zone.test')
        result2 = node_name_for_index(0, 'payload', 'zone.test.')
        assert result1 == result2


class TestInGapName:
    """Tests for in_gap_name function."""
    
    def test_default_suffix(self):
        """Test default 'z' suffix for priming."""
        result = in_gap_name(0, 'zone.test')
        assert result == 'n0000z.zone.test.'
    
    def test_custom_suffix(self):
        """Test custom suffix."""
        result = in_gap_name(0, 'zone.test', suffix='y')
        assert result == 'n0000y.zone.test.'
    
    def test_index_formatting(self):
        """Test index formatting in gap names."""
        result = in_gap_name(42, 'zone.test')
        assert result == 'n0042z.zone.test.'
    
    def test_relative_name(self):
        """Test relative gap name."""
        result = in_gap_name(0, 'zone.test', absolute=False)
        assert result == 'n0000z.zone.test'


class TestVerificationInGapName:
    """Tests for verification_in_gap_name function."""
    
    def test_different_from_priming(self):
        """Verification names should differ from priming names."""
        prime = in_gap_name(0, 'zone.test', suffix='z')
        verify = verification_in_gap_name(0, 'zone.test', variant=0)
        assert prime != verify
    
    def test_variants_are_different(self):
        """Different variants should produce different names."""
        v0 = verification_in_gap_name(0, 'zone.test', variant=0)
        v1 = verification_in_gap_name(0, 'zone.test', variant=1)
        v2 = verification_in_gap_name(0, 'zone.test', variant=2)
        
        assert len({v0, v1, v2}) == 3  # All different
    
    def test_lexicographic_ordering(self):
        """Verification names should still be in the right interval."""
        # The in-gap name should be > n0000.* and < n0001
        verify = verification_in_gap_name(0, 'zone.test', variant=0)
        # Remove zone suffix for comparison
        prefix = verify.replace('.zone.test.', '')
        
        # Should start with n0000 but have suffix
        assert prefix.startswith('n0000')
        assert len(prefix) > 5  # More than just n0000


class TestIsBetween:
    """Tests for is_name_between function."""
    
    def test_basic_between(self):
        """Test basic between check."""
        assert is_name_between('n0000z.zone.test.', 'n0000.a.zone.test.', 'n0001.zone.test.')
    
    def test_not_between_lower(self):
        """Name below lower bound should return False."""
        assert not is_name_between('n0000.zone.test.', 'n0000a.zone.test.', 'n0001.zone.test.')
    
    def test_not_between_upper(self):
        """Name above upper bound should return False."""
        assert not is_name_between('n0002.zone.test.', 'n0000.zone.test.', 'n0001.zone.test.')
    
    def test_case_insensitive(self):
        """Comparison should be case-insensitive."""
        assert is_name_between('N0000Z.zone.test.', 'n0000.a.zone.test.', 'N0001.zone.test.')


class TestExtractIndexFromName:
    """Tests for extract_index_from_name function."""
    
    def test_basic_extraction(self):
        """Test basic index extraction."""
        assert extract_index_from_name('n0000.payload.zone.test.') == 0
        assert extract_index_from_name('n0001.payload.zone.test.') == 1
        assert extract_index_from_name('n0042.payload.zone.test.') == 42
    
    def test_no_leading_zeros_required(self):
        """Index extraction should handle non-zero-padded numbers."""
        # Our format uses zero-padding, but function should still work
        assert extract_index_from_name('n1.payload.zone.test.') == 1
    
    def test_invalid_format(self):
        """Invalid formats should return None."""
        assert extract_index_from_name('invalid.zone.test.') is None
        assert extract_index_from_name('zone.test.') is None
        assert extract_index_from_name('x0000.zone.test.') is None


class TestParseNodeName:
    """Tests for parse_node_name function."""
    
    def test_basic_parsing(self):
        """Test basic node name parsing."""
        result = parse_node_name('n0001.nbswy3dp.zone.test.', 'zone.test')
        assert result is not None
        index, payload = result
        assert index == 1
        assert payload == 'nbswy3dp'
    
    def test_multi_label_payload(self):
        """Test parsing with multi-label payload."""
        result = parse_node_name('n0001.abc.def.ghi.zone.test.', 'zone.test')
        assert result is not None
        index, payload = result
        assert index == 1
        assert payload == 'abc.def.ghi'
    
    def test_case_insensitive(self):
        """Parsing should be case-insensitive."""
        result = parse_node_name('N0001.PAYLOAD.ZONE.TEST.', 'zone.test')
        assert result is not None
        index, payload = result
        assert index == 1
    
    def test_invalid_zone(self):
        """Wrong zone suffix should return None."""
        result = parse_node_name('n0001.payload.other.zone.', 'zone.test')
        assert result is None
    
    def test_invalid_format(self):
        """Invalid node format should return None."""
        result = parse_node_name('invalid.zone.test.', 'zone.test')
        assert result is None


class TestLexicographicOrdering:
    """Tests to verify the lexicographic ordering assumptions."""
    
    def test_node_ordering(self):
        """Verify nodes are ordered correctly."""
        names = [
            'n0000.abc.zone.test.',
            'n0001.def.zone.test.',
            'n0002.ghi.zone.test.',
        ]
        
        # Should be in sorted order
        sorted_names = sorted(names, key=str.lower)
        assert names == sorted_names
    
    def test_gap_name_ordering(self):
        """Verify gap names fall between nodes."""
        node0 = 'n0000.payload.zone.test.'
        gap = 'n0000z.zone.test.'
        node1 = 'n0001.payload.zone.test.'
        
        names = [node0, gap, node1]
        sorted_names = sorted(names, key=str.lower)
        
        # Gap should be between node0 and node1
        assert sorted_names.index(gap) == 1
    
    def test_multiple_gap_names(self):
        """Verify multiple gap names maintain order."""
        names = [
            'n0000.payload.zone.test.',
            'n0000m.zone.test.',  # verification gap
            'n0000y.zone.test.',  # verification gap
            'n0000z.zone.test.',  # priming gap
            'n0001.payload.zone.test.',
        ]
        
        sorted_names = sorted(names, key=str.lower)
        
        # All gaps should be between the two nodes
        node0_idx = sorted_names.index('n0000.payload.zone.test.')
        node1_idx = sorted_names.index('n0001.payload.zone.test.')
        
        assert node0_idx == 0
        assert node1_idx == 4
