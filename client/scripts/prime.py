#!/usr/bin/env python3
"""
NSEC Chain Priming Script

Walks the NSEC chain by querying in-gap names, extracting payload
from the 'next domain name' field in NSEC records.

This script:
1. Queries in-gap names (n0000z.zone.test., n0001z.zone.test., etc.)
2. Receives NXDOMAIN responses with NSEC proofs
3. Extracts the 'next name' from each NSEC to reveal payload chunks
4. Decodes and assembles the complete payload
5. Records query counts for verification comparison
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from nsecchain.ordering import in_gap_name, parse_node_name
from nsecchain.decoder import decode_labels, strip_padding
from nsecchain.parser import query_and_extract_nsec, extract_payload_from_next_name


def count_auth_queries(log_path: str) -> int:
    """
    Count the number of queries in the authoritative server log.
    
    Args:
        log_path: Path to the auth query log file
        
    Returns:
        Number of query lines found
    """
    try:
        if not os.path.exists(log_path):
            return 0
        with open(log_path, 'r') as f:
            lines = f.readlines()
        # Count lines that contain query information
        # BIND9 query log format: "client @... (name): query: name IN type"
        query_count = sum(1 for line in lines if 'query:' in line.lower())
        return query_count
    except Exception as e:
        print(f"[!] Warning: Could not read auth log: {e}")
        return 0


def prime_nsec_chain(
    zone: str,
    resolver_ip: str,
    num_nodes: int,
    timeout: float = 5.0
) -> Tuple[List[str], List[dict]]:
    """
    Prime the recursive resolver cache by walking the NSEC chain.
    
    Args:
        zone: Zone name
        resolver_ip: IP of the recursive resolver
        num_nodes: Expected number of payload nodes
        timeout: Query timeout
        
    Returns:
        Tuple of (payload_chunks, query_details)
    """
    payload_chunks: List[str] = []
    query_details: List[dict] = []
    
    print(f"\n{'='*60}")
    print("PRIMING PHASE - Walking NSEC Chain")
    print(f"{'='*60}")
    print(f"Zone: {zone}")
    print(f"Resolver: {resolver_ip}")
    print(f"Expected nodes: {num_nodes}")
    print()
    
    for i in range(num_nodes):
        # Generate in-gap name for priming (using 'z' suffix)
        gap_name = in_gap_name(i, zone, suffix='z')
        
        print(f"[{i+1}/{num_nodes}] Querying: {gap_name}")
        
        # Query and extract NSEC
        next_name, response = query_and_extract_nsec(gap_name, resolver_ip, timeout)
        
        detail = {
            'index': i,
            'query': gap_name,
            'success': False,
            'next_name': None,
            'payload': None
        }
        
        if next_name:
            next_name_str = next_name.to_text()
            detail['next_name'] = next_name_str
            detail['success'] = True
            
            # Extract payload from next name
            payload = extract_payload_from_next_name(next_name, zone)
            
            if payload:
                detail['payload'] = payload
                payload_chunks.append(payload)
                
                # Parse the next name to show index
                parsed = parse_node_name(next_name_str, zone)
                if parsed:
                    next_idx, _ = parsed
                    print(f"    -> NSEC next: {next_name_str}")
                    print(f"    -> Reveals node n{next_idx:04d} with payload: {payload}")
                else:
                    print(f"    -> NSEC next: {next_name_str} (end marker)")
            else:
                print(f"    -> NSEC next: {next_name_str} (no payload - likely end marker)")
        else:
            print(f"    -> No NSEC found in response")
        
        query_details.append(detail)
        
        # Small delay to ensure proper logging
        time.sleep(0.1)
    
    return payload_chunks, query_details


def decode_payload(chunks: List[str]) -> str:
    """
    Decode payload chunks back to original message.
    
    Args:
        chunks: List of base32 encoded payload strings
        
    Returns:
        Decoded message string
    """
    decoded_bytes = b''
    
    for chunk in chunks:
        try:
            decoded = decode_labels(chunk)
            decoded_bytes += decoded
        except Exception as e:
            print(f"[!] Warning: Failed to decode chunk '{chunk}': {e}")
    
    # Strip padding
    decoded_bytes = strip_padding(decoded_bytes)
    
    try:
        return decoded_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return decoded_bytes.decode('utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(
        description='Prime NSEC cache by walking the chain'
    )
    parser.add_argument(
        '--zone', '-z',
        default=os.environ.get('ZONE_NAME', 'zone.test'),
        help='Zone name'
    )
    parser.add_argument(
        '--resolver', '-r',
        default=os.environ.get('RESOLVER_IP', '172.28.0.3'),
        help='Resolver IP address'
    )
    parser.add_argument(
        '--nodes', '-n',
        type=int,
        default=None,
        help='Number of payload nodes (auto-detect from zone meta if not specified)'
    )
    parser.add_argument(
        '--auth-log', '-l',
        default=os.environ.get('AUTH_LOG_PATH', '/auth-logs/query.log'),
        help='Path to auth query log'
    )
    parser.add_argument(
        '--output', '-o',
        default='/results/prime_results.json',
        help='Output file for results'
    )
    parser.add_argument(
        '--timeout', '-t',
        type=float,
        default=5.0,
        help='Query timeout in seconds'
    )
    
    args = parser.parse_args()
    
    # Auto-detect number of nodes from zone metadata
    num_nodes = args.nodes
    if num_nodes is None:
        meta_path = Path('/auth-zones/zone.meta')
        if meta_path.exists():
            lines = meta_path.read_text().strip().split('\n')
            num_nodes = int(lines[0])
            print(f"[+] Auto-detected {num_nodes} nodes from zone metadata")
        else:
            # Default based on typical message size
            chunk_size = int(os.environ.get('CHUNK_SIZE', '8'))
            message = os.environ.get('MESSAGE', 'hello from nsec cache datastore')
            num_nodes = (len(message) + chunk_size - 1) // chunk_size
            print(f"[+] Estimated {num_nodes} nodes from environment")
    
    # Count auth queries before priming
    auth_queries_before = count_auth_queries(args.auth_log)
    print(f"[+] Auth queries before priming: {auth_queries_before}")
    
    # Prime the cache
    payload_chunks, query_details = prime_nsec_chain(
        zone=args.zone,
        resolver_ip=args.resolver,
        num_nodes=num_nodes,
        timeout=args.timeout
    )
    
    # Small delay for log flush
    time.sleep(0.5)
    
    # Count auth queries after priming
    auth_queries_after = count_auth_queries(args.auth_log)
    priming_queries = auth_queries_after - auth_queries_before
    
    print(f"\n{'='*60}")
    print("PRIMING RESULTS")
    print(f"{'='*60}")
    
    # Decode payload
    if payload_chunks:
        decoded_payload = decode_payload(payload_chunks)
        print(f"Decoded payload: {decoded_payload}")
    else:
        decoded_payload = ""
        print("No payload decoded - NSEC chain may not be properly configured")
    
    print(f"Auth queries during priming: {priming_queries}")
    print(f"Total payload chunks extracted: {len(payload_chunks)}")
    
    # Save results for verification script
    results = {
        'phase': 'prime',
        'zone': args.zone,
        'resolver': args.resolver,
        'num_nodes': num_nodes,
        'payload_chunks': payload_chunks,
        'decoded_payload': decoded_payload,
        'auth_queries_before': auth_queries_before,
        'auth_queries_after': auth_queries_after,
        'priming_queries': priming_queries,
        'query_details': query_details
    }
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"\n[+] Results saved to: {args.output}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
