"""
NSEC Cache Datastore Library

This library provides tools for:
- Encoding/decoding payload into DNS-safe base32 labels
- Generating deterministic node names for the NSEC chain
- Generating "in-gap" names for priming and verification
- Parsing NSEC records to extract next-name payloads
"""

from .encoder import encode_chunk, split_into_labels, chunk_message
from .decoder import decode_labels, decode_chunk
from .ordering import (
    node_name_for_index,
    in_gap_name,
    is_name_between,
    extract_index_from_name,
)
from .parser import (
    extract_nsec_from_response,
    extract_next_name,
    extract_payload_from_next_name,
)

__all__ = [
    # Encoder
    'encode_chunk',
    'split_into_labels', 
    'chunk_message',
    # Decoder
    'decode_labels',
    'decode_chunk',
    # Ordering
    'node_name_for_index',
    'in_gap_name',
    'is_name_between',
    'extract_index_from_name',
    # Parser
    'extract_nsec_from_response',
    'extract_next_name',
    'extract_payload_from_next_name',
]

__version__ = '1.0.0'
