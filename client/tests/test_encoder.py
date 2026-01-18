"""
Unit tests for the encoder module.

Tests base32 encoding, label splitting, and message chunking.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nsecchain.encoder import (
    encode_chunk,
    split_into_labels,
    chunk_message,
    encode_message
)
from nsecchain.decoder import decode_labels, decode_chunk, strip_padding


class TestEncodeChunk:
    """Tests for encode_chunk function."""
    
    def test_basic_encoding(self):
        """Test basic base32 encoding."""
        result = encode_chunk(b'hello')
        assert result == 'nbswy3dp'
    
    def test_encoding_is_lowercase(self):
        """Verify encoding is lowercase for DNS compatibility."""
        result = encode_chunk(b'TEST')
        assert result == result.lower()
        assert result.isalnum()
    
    def test_no_padding_in_output(self):
        """Verify no base32 padding characters in output."""
        result = encode_chunk(b'hi')
        assert '=' not in result
    
    def test_empty_bytes(self):
        """Test encoding empty bytes."""
        result = encode_chunk(b'')
        assert result == ''
    
    def test_various_lengths(self):
        """Test encoding various byte lengths."""
        for length in [1, 2, 3, 4, 5, 6, 7, 8, 16, 32]:
            data = b'x' * length
            result = encode_chunk(data)
            assert result  # Non-empty result
            assert result.isalnum()


class TestSplitIntoLabels:
    """Tests for split_into_labels function."""
    
    def test_short_string(self):
        """Short strings should be single label."""
        result = split_into_labels('hello')
        assert result == ['hello']
    
    def test_exact_boundary(self):
        """Test string exactly at label limit."""
        data = 'a' * 63
        result = split_into_labels(data, max_label_len=63)
        assert len(result) == 1
        assert result[0] == data
    
    def test_split_at_boundary(self):
        """Test string that needs splitting."""
        data = 'a' * 64
        result = split_into_labels(data, max_label_len=63)
        assert len(result) == 2
        assert result[0] == 'a' * 63
        assert result[1] == 'a'
    
    def test_multiple_splits(self):
        """Test string needing multiple splits."""
        data = 'a' * 200
        result = split_into_labels(data, max_label_len=63)
        assert len(result) == 4  # 63 + 63 + 63 + 11
    
    def test_empty_string(self):
        """Test empty string."""
        result = split_into_labels('')
        assert result == []
    
    def test_custom_label_length(self):
        """Test custom max label length."""
        data = 'abcdefghij'
        result = split_into_labels(data, max_label_len=3)
        assert result == ['abc', 'def', 'ghi', 'j']


class TestChunkMessage:
    """Tests for chunk_message function."""
    
    def test_exact_fit(self):
        """Message that fits exactly in chunks."""
        result = chunk_message(b'abcdefgh', chunk_size=4)
        assert result == [b'abcd', b'efgh']
    
    def test_needs_padding(self):
        """Message that needs padding in last chunk."""
        result = chunk_message(b'hello', chunk_size=8)
        assert len(result) == 1
        assert len(result[0]) == 8
        assert result[0] == b'hello___'
    
    def test_multiple_chunks_with_padding(self):
        """Multiple chunks with last needing padding."""
        result = chunk_message(b'hello world', chunk_size=4)
        assert len(result) == 3
        assert result[0] == b'hell'
        assert result[1] == b'o wo'
        assert result[2] == b'rld_'
    
    def test_empty_message(self):
        """Empty message should produce padding-only chunk."""
        result = chunk_message(b'', chunk_size=4)
        assert len(result) == 1
        assert result[0] == b'____'


class TestRoundTrip:
    """Tests for encode/decode round trip."""
    
    def test_basic_roundtrip(self):
        """Basic encode/decode round trip."""
        original = b'hello'
        encoded = encode_chunk(original)
        decoded = decode_chunk(encoded)
        assert decoded == original
    
    def test_roundtrip_various_lengths(self):
        """Round trip with various data lengths."""
        for length in [1, 2, 3, 4, 5, 8, 16, 32]:
            original = bytes(range(length % 256)) * (length // 256 + 1)
            original = original[:length]
            encoded = encode_chunk(original)
            decoded = decode_chunk(encoded)
            assert decoded == original
    
    def test_roundtrip_with_padding(self):
        """Round trip with underscore padding."""
        original = b'hello___'
        encoded = encode_chunk(original)
        decoded = decode_chunk(encoded)
        assert decoded == original
        
        # After strip_padding
        stripped = strip_padding(decoded)
        assert stripped == b'hello'


class TestEncodeMessage:
    """Tests for encode_message convenience function."""
    
    def test_encode_short_message(self):
        """Encode a short message."""
        result = encode_message('hello', chunk_size=8)
        assert len(result) == 1
    
    def test_encode_long_message(self):
        """Encode a longer message."""
        result = encode_message('hello from nsec cache datastore', chunk_size=8)
        assert len(result) == 5  # 34 bytes / 8 = 4.25 -> 5 chunks
