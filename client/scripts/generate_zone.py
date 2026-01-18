#!/usr/bin/env python3
"""
Zone Generator Script

Generates a DNS zone file with payload encoded in domain names.
This script is run by the auth container at startup.

Can also be run standalone for testing zone generation.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports when run standalone
sys.path.insert(0, str(Path(__file__).parent.parent))

from nsecchain.encoder import encode_chunk, chunk_message, split_into_labels


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
    
    print(f"[+] Encoding message: {message}")
    print(f"[+] Chunk size: {chunk_size} bytes")
    print(f"[+] Number of chunks: {len(chunks)}")
    
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

; ============================================================
; Payload nodes - each name encodes a chunk of the message
; These will be linked via NSEC records after signing
; ============================================================
"""
    
    # Generate node records
    for i, chunk in enumerate(chunks):
        encoded = encode_chunk(chunk)
        labels = split_into_labels(encoded)
        payload_part = '.'.join(labels)
        
        # The full name relative to zone
        node_name = f"n{i:04d}.{payload_part}"
        
        zone_content += f"{node_name}    IN  A   192.0.2.{10 + i}\n"
        print(f"    Node {i}: {node_name}.{zone}. -> {chunk}")
    
    # Add a sentinel/end marker node (helps with NSEC chain termination)
    end_index = len(chunks)
    zone_content += f"\n; End marker\nn{end_index:04d}.end    IN  A   192.0.2.254\n"
    
    # Write the zone file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(zone_content)
    
    print(f"[+] Zone file written to: {output_path}")
    
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
        default='zone.test.db',
        help='Output zone file path'
    )
    
    args = parser.parse_args()
    
    output_path = Path(args.output)
    
    num_nodes = generate_zone_file(
        zone=args.zone,
        message=args.message,
        chunk_size=args.chunk_size,
        ttl=args.ttl,
        output_path=output_path
    )
    
    print(f"[+] Generated {num_nodes} payload nodes")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
