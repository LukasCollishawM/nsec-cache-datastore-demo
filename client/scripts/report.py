#!/usr/bin/env python3
"""
NSEC Cache Datastore Demo Report Generator

Produces a human-friendly summary of the demo results, showing:
- Decoded payload
- Priming statistics
- Verification statistics
- Verdict on RFC 8198 aggressive negative caching
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime


def load_results(prime_path: str, verify_path: str) -> tuple:
    """Load priming and verification results."""
    prime_results = None
    verify_results = None
    
    if Path(prime_path).exists():
        prime_results = json.loads(Path(prime_path).read_text())
    
    if Path(verify_path).exists():
        verify_results = json.loads(Path(verify_path).read_text())
    
    return prime_results, verify_results


def generate_report(prime_results: dict, verify_results: dict) -> str:
    """Generate the demo report."""
    
    width = 70
    
    lines = []
    lines.append("=" * width)
    lines.append("NSEC CACHE DATASTORE DEMO REPORT".center(width))
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(width))
    lines.append("=" * width)
    lines.append("")
    
    # Configuration
    if prime_results:
        lines.append("CONFIGURATION")
        lines.append("-" * 40)
        lines.append(f"  Zone:              {prime_results.get('zone', 'unknown')}")
        lines.append(f"  Resolver:          {prime_results.get('resolver', 'unknown')}")
        lines.append(f"  Payload nodes:     {prime_results.get('num_nodes', 'unknown')}")
        lines.append("")
    
    # Payload
    lines.append("DECODED PAYLOAD")
    lines.append("-" * 40)
    
    if prime_results and prime_results.get('decoded_payload'):
        payload = prime_results['decoded_payload']
        lines.append(f"  From priming:      \"{payload}\"")
    
    if verify_results and verify_results.get('decoded_payload'):
        payload = verify_results['decoded_payload']
        lines.append(f"  From verification: \"{payload}\"")
    
    lines.append("")
    
    # Priming Statistics
    lines.append("PRIMING PHASE")
    lines.append("-" * 40)
    
    if prime_results:
        chunks = len(prime_results.get('payload_chunks', []))
        auth_before = prime_results.get('auth_queries_before', 0)
        auth_after = prime_results.get('auth_queries_after', 0)
        priming_queries = prime_results.get('priming_queries', auth_after - auth_before)
        
        lines.append(f"  Payload chunks extracted:    {chunks}")
        lines.append(f"  Auth queries (before):       {auth_before}")
        lines.append(f"  Auth queries (after):        {auth_after}")
        lines.append(f"  New auth queries:            {priming_queries}")
        lines.append("")
        lines.append("  [Expected: Priming SHOULD contact authoritative to fill cache]")
    else:
        lines.append("  [No priming results available]")
    
    lines.append("")
    
    # Verification Statistics
    lines.append("VERIFICATION PHASE")
    lines.append("-" * 40)
    
    if verify_results:
        synthesis = verify_results.get('synthesis_count', 0)
        total = verify_results.get('num_nodes', 0)
        auth_before = verify_results.get('auth_queries_before', 0)
        auth_after = verify_results.get('auth_queries_after', 0)
        delta = verify_results.get('delta', auth_after - auth_before)
        
        lines.append(f"  Successful cache hits:       {synthesis}/{total}")
        lines.append(f"  Auth queries (before):       {auth_before}")
        lines.append(f"  Auth queries (after):        {auth_after}")
        lines.append(f"  New auth queries (Δ):        {delta}")
        lines.append("")
        lines.append("  [Expected: Verification should NOT contact authoritative (Δ=0)]")
    else:
        lines.append("  [No verification results available]")
    
    lines.append("")
    
    # Verdict
    lines.append("=" * width)
    lines.append("VERDICT".center(width))
    lines.append("=" * width)
    lines.append("")
    
    if verify_results:
        delta = verify_results.get('delta', -1)
        verdict = verify_results.get('verdict', 'UNKNOWN')
        
        if delta == 0:
            lines.append("  ╔════════════════════════════════════════════════════════════╗")
            lines.append("  ║                        SUCCESS                             ║")
            lines.append("  ╠════════════════════════════════════════════════════════════╣")
            lines.append("  ║  RFC 8198 aggressive negative caching CONFIRMED            ║")
            lines.append("  ║                                                            ║")
            lines.append("  ║  The recursive resolver served NXDOMAIN responses with     ║")
            lines.append("  ║  NSEC proofs for UNSEEN names using only cached data.      ║")
            lines.append("  ║                                                            ║")
            lines.append("  ║  Δ = 0: No new queries to authoritative during verify.     ║")
            lines.append("  ╚════════════════════════════════════════════════════════════╝")
        else:
            lines.append("  ╔════════════════════════════════════════════════════════════╗")
            lines.append("  ║                     UNEXPECTED RESULT                      ║")
            lines.append("  ╠════════════════════════════════════════════════════════════╣")
            lines.append(f"  ║  Δ = {delta}: Authoritative was contacted during verify".ljust(62) + "║")
            lines.append("  ║                                                            ║")
            lines.append("  ║  Possible causes:                                          ║")
            lines.append("  ║  - NSEC cache TTL expired between prime and verify         ║")
            lines.append("  ║  - aggressive-nsec not enabled in Unbound                  ║")
            lines.append("  ║  - DNSSEC validation failed                                ║")
            lines.append("  ╚════════════════════════════════════════════════════════════╝")
    else:
        lines.append("  [Cannot determine verdict - verification results missing]")
    
    lines.append("")
    lines.append("=" * width)
    lines.append("END OF REPORT".center(width))
    lines.append("=" * width)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Generate NSEC cache datastore demo report'
    )
    parser.add_argument(
        '--prime-results', '-p',
        default='/results/prime_results.json',
        help='Path to priming results JSON'
    )
    parser.add_argument(
        '--verify-results', '-v',
        default='/results/verify_results.json',
        help='Path to verification results JSON'
    )
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='Output file (default: stdout)'
    )
    
    args = parser.parse_args()
    
    # Load results
    prime_results, verify_results = load_results(
        args.prime_results,
        args.verify_results
    )
    
    # Generate report
    report = generate_report(prime_results, verify_results)
    
    # Output
    if args.output:
        Path(args.output).write_text(report)
        print(f"[+] Report saved to: {args.output}")
    else:
        print(report)
    
    # Return exit code based on verdict
    if verify_results and verify_results.get('delta', -1) == 0:
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
