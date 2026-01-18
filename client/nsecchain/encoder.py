"""
Payload Encoder for NSEC Cache Datastore

Encodes arbitrary data into DNS-safe domain name labels using base32.
Base32 is chosen because:
- Uses only alphanumeric characters (A-Z, 2-7)
- No special characters that could cause DNS issues
- Case-insensitive (DNS is case-insensitive)
"""

import base64
from typing import List


def encode_chunk(chunk: bytes) -> str:
    """
    Encode a chunk of bytes as DNS-safe base32 string.
    
    Uses RFC 4648 base32 encoding without padding, lowercased
    for DNS convention compliance.
    
    Args:
        chunk: Raw bytes to encode (typically 8-16 bytes)
        
    Returns:
        Lowercase base32 encoded string without padding
        
    Example:
        >>> encode_chunk(b'hello')
        'nbswy3dp'
    """
    encoded = base64.b32encode(chunk).decode('ascii')
    # Remove padding and lowercase for DNS compatibility
    return encoded.rstrip('=').lower()


def split_into_labels(encoded: str, max_label_len: int = 63) -> List[str]:
    """
    Split an encoded string into DNS-safe labels.
    
    DNS labels are limited to 63 characters each. This function
    splits longer encoded strings into multiple labels.
    
    Args:
        encoded: The base32 encoded string
        max_label_len: Maximum characters per label (DNS limit is 63)
        
    Returns:
        List of label strings, each <= max_label_len
        
    Example:
        >>> split_into_labels('abcdefghij', max_label_len=4)
        ['abcd', 'efgh', 'ij']
    """
    if not encoded:
        return []
    return [encoded[i:i + max_label_len] 
            for i in range(0, len(encoded), max_label_len)]


def chunk_message(message: bytes, chunk_size: int) -> List[bytes]:
    """
    Split a message into fixed-size chunks.
    
    The last chunk is padded with underscores if needed to
    maintain consistent sizing.
    
    Args:
        message: The message bytes to chunk
        chunk_size: Size of each chunk in bytes
        
    Returns:
        List of byte chunks, each exactly chunk_size bytes
        
    Example:
        >>> chunk_message(b'hello', 3)
        [b'hel', b'lo_']
    """
    chunks = []
    for i in range(0, len(message), chunk_size):
        chunk = message[i:i + chunk_size]
        # Pad last chunk with underscores
        if len(chunk) < chunk_size:
            chunk = chunk + b'_' * (chunk_size - len(chunk))
        chunks.append(chunk)
    
    # Ensure at least one chunk
    if not chunks:
        chunks = [b'_' * chunk_size]
    
    return chunks


def encode_message(message: str, chunk_size: int = 8) -> List[str]:
    """
    Encode a complete message into a list of DNS-safe label strings.
    
    This is a convenience function that combines chunking and encoding.
    
    Args:
        message: The message string to encode
        chunk_size: Size of each chunk in bytes before encoding
        
    Returns:
        List of base32 encoded strings, one per chunk
        
    Example:
        >>> encode_message('hello world', chunk_size=8)
        ['nbswy3dpeb3w64tm', 'onqxizi_']  # approximate
    """
    message_bytes = message.encode('utf-8')
    chunks = chunk_message(message_bytes, chunk_size)
    return [encode_chunk(c) for c in chunks]
