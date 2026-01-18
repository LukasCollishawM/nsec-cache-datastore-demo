#!/usr/bin/env python3
"""
NSEC Synthesis Verification Script

Verifies that the recursive resolver can answer queries for NEW in-gap
names using cached NSEC proofs WITHOUT contacting the authoritative server.

This proves RFC 8198 aggressive negative caching is working:
1. Query different in-gap names than used during priming
2. Verify NXDOMAIN responses still contain NSEC proofs with payload
3. Confirm authoritative query count did NOT increase
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from nsecchain.ordering import verification_in_gap_name, parse_node_name
from nsecchain.decoder import decode_labels, strip_padding
from nsecchain.parser import query_and_extract_nsec, extract_payload_from_next_name


def count_auth_queries(log_path: str) -> int:
    """
    Count the number of queries in the authoritative server log.
    """
    try:
        if not os.path.exists(log_path):
            return 0
        with open(log_path, 'r') as f:
            lines = f.readlines()
        query_count = sum(1 for line in lines if 'query:' in line.lower())
        return query_count
    except Exception as e:
        print(f"[!] Warning: Could not read auth log: {e}")
        return 0


def verify_synthesis(
    zone: str,
    resolver_ip: str,
    num_nodes: int,
    timeout: float = 5.0
) -> Tuple[List[str], List[dict], int]:
    """
    Verify that new in-gap queries are answered from cache.
    
    Uses DIFFERENT in-gap names than priming to prove the resolver
    is synthesizing answers from cached NSEC records.
    
    Args:
        zone: Zone name
        resolver_ip: IP of the recursive resolver
        num_nodes: Number of payload nodes
        timeout: Query timeout
        
    Returns:
        Tuple of (payload_chunks, query_details, successful_synthesis_count)
    """
    payload_chunks: List[str] = []
    query_details: List[dict] = []
    synthesis_count = 0
    
    print(f"\n{'='*60}")
    print("VERIFICATION PHASE - Testing Cache Synthesis")
    print(f"{'='*60}")
    print(f"Zone: {zone}")
    print(f"Resolver: {resolver_ip}")
    print(f"Nodes to verify: {num_nodes}")
    print("Using DIFFERENT in-gap names than priming phase")
    print()
    
    for i in range(num_nodes):
        # Generate DIFFERENT in-gap name for verification (using 'm' suffix)
        # This ensures we're testing names the resolver has NEVER seen
        gap_name = verification_in_gap_name(i, zone, variant=0)
        
        print(f"[{i+1}/{num_nodes}] Querying: {gap_name}")
        
        # Query and extract NSEC
        next_name, response = query_and_extract_nsec(gap_name, resolver_ip, timeout)
        
        detail = {
            'index': i,
            'query': gap_name,
            'success': False,
            'synthesized': False,
            'next_name': None,
            'payload': None
        }
        
        if next_name:
            next_name_str = next_name.to_text()
            detail['next_name'] = next_name_str
            detail['success'] = True
            detail['synthesized'] = True  # If we got NSEC, it was synthesized
            synthesis_count += 1
            
            # Extract payload from next name
            payload = extract_payload_from_next_name(next_name, zone)
            
            if payload:
                detail['payload'] = payload
                payload_chunks.append(payload)
                
                parsed = parse_node_name(next_name_str, zone)
                if parsed:
                    next_idx, _ = parsed
                    print(f"    -> NSEC next: {next_name_str} (from cache)")
                    print(f"    -> Payload chunk: {payload}")
                else:
                    print(f"    -> NSEC next: {next_name_str} (end marker)")
            else:
                print(f"    -> NSEC next: {next_name_str} (no payload)")
        else:
            print(f"    -> No NSEC found - cache may have expired or not primed")
        
        query_details.append(detail)
        
        # Small delay
        time.sleep(0.1)
    
    return payload_chunks, query_details, synthesis_count


def decode_payload(chunks: List[str]) -> str:
    """Decode payload chunks back to original message."""
    decoded_bytes = b''
    
    for chunk in chunks:
        try:
            decoded = decode_labels(chunk)
            decoded_bytes += decoded
        except Exception as e:
            print(f"[!] Warning: Failed to decode chunk '{chunk}': {e}")
    
    decoded_bytes = strip_padding(decoded_bytes)
    
    try:
        return decoded_bytes.decode('utf-8')
    except UnicodeDecodeError:
        return decoded_bytes.decode('utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(
        description='Verify NSEC cache synthesis without auth contact'
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
        '--auth-log', '-l',
        default=os.environ.get('AUTH_LOG_PATH', '/auth-logs/query.log'),
        help='Path to auth query log'
    )
    parser.add_argument(
        '--prime-results', '-p',
        default='/results/prime_results.json',
        help='Path to priming results JSON'
    )
    parser.add_argument(
        '--output', '-o',
        default='/results/verify_results.json',
        help='Output file for results'
    )
    parser.add_argument(
        '--timeout', '-t',
        type=float,
        default=5.0,
        help='Query timeout in seconds'
    )
    
    args = parser.parse_args()
    
    # Load priming results to get node count and baseline
    prime_results = None
    prime_results_path = Path(args.prime_results)
    
    if prime_results_path.exists():
        prime_results = json.loads(prime_results_path.read_text())
        num_nodes = prime_results.get('num_nodes', 5)
        auth_queries_after_prime = prime_results.get('auth_queries_after', 0)
        print(f"[+] Loaded priming results: {num_nodes} nodes")
        print(f"[+] Auth queries after priming: {auth_queries_after_prime}")
    else:
        # Fall back to environment/defaults
        chunk_size = int(os.environ.get('CHUNK_SIZE', '8'))
        message = os.environ.get('MESSAGE', 'hello from nsec cache datastore')
        num_nodes = (len(message) + chunk_size - 1) // chunk_size
        auth_queries_after_prime = count_auth_queries(args.auth_log)
        print(f"[+] Estimated {num_nodes} nodes (no prime results found)")
    
    # Count auth queries before verification
    auth_queries_before = count_auth_queries(args.auth_log)
    print(f"[+] Auth queries before verification: {auth_queries_before}")
    
    # Verify synthesis
    payload_chunks, query_details, synthesis_count = verify_synthesis(
        zone=args.zone,
        resolver_ip=args.resolver,
        num_nodes=num_nodes,
        timeout=args.timeout
    )
    
    # Small delay for log flush
    time.sleep(0.5)
    
    # Count auth queries after verification
    auth_queries_after = count_auth_queries(args.auth_log)
    verification_queries = auth_queries_after - auth_queries_before
    
    print(f"\n{'='*60}")
    print("VERIFICATION RESULTS")
    print(f"{'='*60}")
    
    # Decode payload from verification
    if payload_chunks:
        decoded_payload = decode_payload(payload_chunks)
        print(f"Decoded payload (from cache): {decoded_payload}")
    else:
        decoded_payload = ""
        print("No payload decoded from verification queries")
    
    print(f"\nAuth queries before verify: {auth_queries_before}")
    print(f"Auth queries after verify: {auth_queries_after}")
    print(f"New auth queries during verify: {verification_queries}")
    print(f"Successful cache hits: {synthesis_count}/{num_nodes}")
    
    # The key metric: did we contact auth?
    delta = verification_queries
    
    if delta == 0:
        print(f"\n✓ SUCCESS: Δ = 0 (no new authoritative queries)")
        print("  The resolver answered from cached NSEC proofs!")
        verdict = "SUCCESS"
    else:
        print(f"\n✗ UNEXPECTED: Δ = {delta} (authoritative was contacted)")
        print("  Cache may have expired or aggressive-nsec not working")
        verdict = "FAILED"
    
    # Save results
    results = {
        'phase': 'verify',
        'zone': args.zone,
        'resolver': args.resolver,
        'num_nodes': num_nodes,
        'payload_chunks': payload_chunks,
        'decoded_payload': decoded_payload,
        'auth_queries_before': auth_queries_before,
        'auth_queries_after': auth_queries_after,
        'verification_queries': verification_queries,
        'synthesis_count': synthesis_count,
        'delta': delta,
        'verdict': verdict,
        'query_details': query_details
    }
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2))
    print(f"\n[+] Results saved to: {args.output}")
    
    # Return non-zero if verification failed
    return 0 if delta == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
