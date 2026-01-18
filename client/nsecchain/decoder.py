"""
Payload Decoder for NSEC Cache Datastore

Decodes base32-encoded DNS labels back to original payload bytes.
"""

import base64
from typing import List, Optional


def decode_labels(labels: str) -> bytes:
    """
    Decode base32-encoded DNS labels back to bytes.
    
    Handles labels that may be dot-separated (from multi-label encoding)
    and adds proper base32 padding.
    
    Args:
        labels: Base32 encoded string (may contain dots)
        
    Returns:
        Decoded bytes
        
    Example:
        >>> decode_labels('nbswy3dp')
        b'hello'
    """
    # Remove dots if present (multi-label encoding)
    clean = labels.replace('.', '')
    
    # Uppercase for base32 decoding
    clean = clean.upper()
    
    # Add padding (base32 requires padding to multiple of 8)
    padding_needed = (8 - len(clean) % 8) % 8
    clean = clean + '=' * padding_needed
    
    try:
        return base64.b32decode(clean)
    except Exception as e:
        raise ValueError(f"Failed to decode base32 labels '{labels}': {e}")


def decode_chunk(encoded: str) -> bytes:
    """
    Decode a single encoded chunk.
    
    Alias for decode_labels for API consistency.
    
    Args:
        encoded: Base32 encoded string
        
    Returns:
        Decoded bytes
    """
    return decode_labels(encoded)


def strip_padding(data: bytes, padding_char: bytes = b'_') -> bytes:
    """
    Strip padding characters from decoded data.
    
    The encoder pads chunks with underscores; this removes them.
    
    Args:
        data: Decoded bytes potentially containing padding
        padding_char: The padding character to strip (default: b'_')
        
    Returns:
        Data with trailing padding removed
    """
    return data.rstrip(padding_char)


def decode_payload_chunks(encoded_chunks: List[str]) -> bytes:
    """
    Decode multiple encoded chunks and concatenate.
    
    Args:
        encoded_chunks: List of base32 encoded strings
        
    Returns:
        Concatenated decoded bytes with padding stripped
    """
    decoded = b''.join(decode_labels(c) for c in encoded_chunks)
    return strip_padding(decoded)


def extract_payload_labels(fqdn: str, zone: str) -> Optional[str]:
    """
    Extract the payload labels from a fully qualified domain name.
    
    Given a name like 'n0001.nbswy3dp.zone.test.', extract 'nbswy3dp'.
    
    Args:
        fqdn: Fully qualified domain name
        zone: The zone suffix (e.g., 'zone.test' or 'zone.test.')
        
    Returns:
        The payload labels portion, or None if format doesn't match
        
    Example:
        >>> extract_payload_labels('n0001.nbswy3dp.zone.test.', 'zone.test')
        'nbswy3dp'
    """
    # Normalize zone
    zone = zone.rstrip('.')
    fqdn = fqdn.rstrip('.')
    
    # Remove zone suffix
    if not fqdn.endswith('.' + zone):
        return None
    
    # Remove zone suffix
    prefix = fqdn[:-len(zone) - 1]  # -1 for the dot
    
    # Split into labels
    labels = prefix.split('.')
    
    # First label is the index (e.g., 'n0001')
    # Remaining labels are the payload
    if len(labels) < 2:
        return None
    
    # Check if first label matches index pattern
    if not (labels[0].startswith('n') and labels[0][1:].isdigit()):
        return None
    
    # Return payload labels joined
    return '.'.join(labels[1:])
