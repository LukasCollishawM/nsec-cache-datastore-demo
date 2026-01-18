#!/usr/bin/env python3
"""
Zone Generator for NSEC Cache Datastore Demo

Generates a DNS zone file with payload encoded in domain names.
The NSEC chain will link these names, allowing payload extraction
via the 'next domain name' field in NSEC records.

Naming scheme: n{index:04d}.{base32_chunk}.zone.test.
"""

import argparse
import base64
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple


def encode_chunk_base32(chunk: bytes) -> str:
    """
    Encode a chunk of bytes as base32 without padding.
    
    Base32 is DNS-safe (uses only A-Z and 2-7), and we lowercase
    for consistency with DNS conventions.
    
    Args:
        chunk: Raw bytes to encode
        
    Returns:
        Lowercase base32 string without padding
    """
    encoded = base64.b32encode(chunk).decode('ascii').rstrip('=').lower()
    return encoded


def split_into_labels(encoded: str, max_label_len: int = 63) -> List[str]:
    """
    Split an encoded string into DNS-safe labels (max 63 chars each).
    
    Args:
        encoded: The encoded string to split
        max_label_len: Maximum length per label (DNS limit is 63)
        
    Returns:
        List of label strings
    """
    return [encoded[i:i+max_label_len] for i in range(0, len(encoded), max_label_len)]


def chunk_message(message: bytes, chunk_size: int) -> List[bytes]:
    """
    Split a message into fixed-size chunks, padding the last if needed.
    
    Args:
        message: The message bytes to chunk
        chunk_size: Size of each chunk in bytes
        
    Returns:
        List of byte chunks
    """
    chunks = []
    for i in range(0, len(message), chunk_size):
        chunk = message[i:i+chunk_size]
        # Pad last chunk with underscores if needed
        if len(chunk) < chunk_size:
            chunk = chunk + b'_' * (chunk_size - len(chunk))
        chunks.append(chunk)
    return chunks


def generate_node_name(index: int, chunk: bytes, zone: str) -> Tuple[str, str]:
    """
    Generate a node name for a payload chunk.
    
    Args:
        index: Node index (0-based)
        chunk: The payload chunk bytes
        zone: The zone name (without trailing dot)
        
    Returns:
        Tuple of (full_name, encoded_payload_label)
    """
    encoded = encode_chunk_base32(chunk)
    labels = split_into_labels(encoded)
    payload_part = '.'.join(labels)
    
    # Format: n{index:04d}.{payload}.zone.test.
    full_name = f"n{index:04d}.{payload_part}.{zone}."
    
    return full_name, payload_part


def generate_zone_file(
    zone: str,
    message: str,
    chunk_size: int,
    ttl: int,
    output_path: Path
) -> int:
    """
    Generate a complete unsigned zone file.
    
    Args:
        zone: Zone name (without trailing dot)
        message: Message to encode in the NSEC chain
        chunk_size: Bytes per chunk
        ttl: TTL for records
        output_path: Path to write the zone file
        
    Returns:
        Number of nodes created
    """
    message_bytes = message.encode('utf-8')
    chunks = chunk_message(message_bytes, chunk_size)
    
    # Serial number from current date/time
    serial = datetime.now().strftime('%Y%m%d%H')
    
    # Build zone content
    zone_content = f"""$ORIGIN {zone}.
$TTL {ttl}

; SOA Record
@   IN  SOA ns1.{zone}. admin.{zone}. (
        {serial}    ; Serial
        3600        ; Refresh (1 hour)
        900         ; Retry (15 minutes)
        604800      ; Expire (1 week)
        {ttl}       ; Minimum TTL (negative cache)
    )

; NS Record
@       IN  NS  ns1.{zone}.
ns1     IN  A   192.0.2.1

; Payload nodes - each name encodes a chunk of the message
; These will be linked via NSEC records after signing
"""
    
    # Generate node records
    for i, chunk in enumerate(chunks):
        node_name, _ = generate_node_name(i, chunk, zone)
        # Remove the trailing zone and dot for the record
        relative_name = node_name.replace(f'.{zone}.', '')
        zone_content += f"{relative_name}    IN  A   192.0.2.{i + 10}\n"
    
    # Add a sentinel/end marker node
    end_index = len(chunks)
    zone_content += f"n{end_index:04d}.end    IN  A   192.0.2.254\n"
    
    # Write the zone file
    output_path.write_text(zone_content)
    
    print(f"[+] Generated zone file with {len(chunks)} payload nodes")
    print(f"[+] Message: {message}")
    print(f"[+] Chunk size: {chunk_size} bytes")
    print(f"[+] Output: {output_path}")
    
    return len(chunks)


def main():
    parser = argparse.ArgumentParser(
        description='Generate DNS zone with payload encoded in node names'
    )
    parser.add_argument(
        '--zone', '-z',
        default='zone.test',
        help='Zone name (default: zone.test)'
    )
    parser.add_argument(
        '--message', '-m',
        default='hello from nsec cache datastore',
        help='Message to encode'
    )
    parser.add_argument(
        '--chunk-size', '-c',
        type=int,
        default=8,
        help='Chunk size in bytes (default: 8)'
    )
    parser.add_argument(
        '--ttl', '-t',
        type=int,
        default=60,
        help='TTL for records (default: 60)'
    )
    parser.add_argument(
        '--output', '-o',
        default='/var/cache/bind/zones/zone.test.db',
        help='Output zone file path'
    )
    
    args = parser.parse_args()
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    num_nodes = generate_zone_file(
        zone=args.zone,
        message=args.message,
        chunk_size=args.chunk_size,
        ttl=args.ttl,
        output_path=output_path
    )
    
    # Write metadata for other scripts
    meta_path = output_path.parent / 'zone.meta'
    meta_path.write_text(f"{num_nodes}\n{args.message}\n{args.chunk_size}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
