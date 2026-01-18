"""
DNS Name Ordering and Generation for NSEC Chain

Provides utilities for:
- Generating node names with encoded payloads
- Generating "in-gap" names for priming/verification
- Checking lexicographic ordering of DNS names
"""

import re
from typing import Optional, Tuple


def node_name_for_index(
    index: int,
    encoded_payload: str,
    zone: str,
    absolute: bool = True
) -> str:
    """
    Generate the node name for a given index and payload.
    
    Node names follow the format: n{index:04d}.{payload}.{zone}
    
    Args:
        index: Node index (0-based)
        encoded_payload: Base32 encoded payload (may contain dots)
        zone: Zone name (e.g., 'zone.test')
        absolute: If True, append trailing dot for absolute name
        
    Returns:
        The complete node name
        
    Example:
        >>> node_name_for_index(0, 'nbswy3dp', 'zone.test')
        'n0000.nbswy3dp.zone.test.'
    """
    zone = zone.rstrip('.')
    name = f"n{index:04d}.{encoded_payload}.{zone}"
    if absolute:
        name += '.'
    return name


def in_gap_name(
    index: int,
    zone: str,
    suffix: str = 'z',
    absolute: bool = True
) -> str:
    """
    Generate a name that falls lexicographically between node[index] and node[index+1].
    
    For priming, we use 'z' suffix: n0000z.zone.test.
    For verification, we use different suffixes: n0000y.zone.test., n0000m.zone.test.
    
    The key insight is that 'n0000z' comes after 'n0000.<anything>' but before 'n0001'
    in DNS canonical ordering.
    
    Args:
        index: The base node index
        zone: Zone name
        suffix: Character to append (default 'z' for priming)
        absolute: If True, append trailing dot
        
    Returns:
        An in-gap name string
        
    Example:
        >>> in_gap_name(0, 'zone.test', 'z')
        'n0000z.zone.test.'
        >>> in_gap_name(0, 'zone.test', 'y')
        'n0000y.zone.test.'
    """
    zone = zone.rstrip('.')
    name = f"n{index:04d}{suffix}.{zone}"
    if absolute:
        name += '.'
    return name


def verification_in_gap_name(index: int, zone: str, variant: int = 0) -> str:
    """
    Generate an in-gap name for verification (different from priming).
    
    Uses different suffixes to ensure these are distinct names that
    the resolver hasn't seen before, but still fall in the same
    NSEC interval.
    
    Args:
        index: The base node index
        zone: Zone name
        variant: Which variant (0='m', 1='k', 2='j', etc.)
        
    Returns:
        A verification in-gap name
    """
    # Use suffixes that are lexicographically between typical payloads
    # and come before 'z' (used for priming)
    suffixes = ['m', 'k', 'j', 'h', 'g', 'f', 'e', 'd', 'c', 'b']
    suffix = suffixes[variant % len(suffixes)]
    return in_gap_name(index, zone, suffix)


def is_name_between(name: str, lower: str, upper: str) -> bool:
    """
    Check if a name falls lexicographically between two bounds.
    
    Uses DNS canonical ordering (case-insensitive, label-by-label).
    
    Args:
        name: The name to check
        lower: Lower bound (exclusive)
        upper: Upper bound (exclusive)
        
    Returns:
        True if lower < name < upper in canonical order
    """
    # Normalize to lowercase for comparison
    name = name.lower().rstrip('.')
    lower = lower.lower().rstrip('.')
    upper = upper.lower().rstrip('.')
    
    # Simple string comparison works for our naming scheme
    # because we use consistent formatting (n0000, n0001, etc.)
    return lower < name < upper


def extract_index_from_name(name: str) -> Optional[int]:
    """
    Extract the node index from a node name.
    
    Args:
        name: A node name like 'n0001.payload.zone.test.'
        
    Returns:
        The index (1 in the example), or None if not a valid node name
    """
    # Get the first label
    first_label = name.split('.')[0].lower()
    
    # Check pattern: n followed by digits
    match = re.match(r'^n(\d+)$', first_label)
    if match:
        return int(match.group(1))
    
    return None


def parse_node_name(name: str, zone: str) -> Optional[Tuple[int, str]]:
    """
    Parse a node name into its components.
    
    Args:
        name: Full node name like 'n0001.nbswy3dp.zone.test.'
        zone: Zone name
        
    Returns:
        Tuple of (index, encoded_payload) or None if invalid
    """
    zone = zone.rstrip('.')
    name = name.rstrip('.').lower()
    
    # Check zone suffix
    zone_suffix = '.' + zone.lower()
    if not name.endswith(zone_suffix):
        return None
    
    # Remove zone
    prefix = name[:-len(zone_suffix)]
    
    # Split into parts
    parts = prefix.split('.')
    if len(parts) < 2:
        return None
    
    # Extract index from first part
    index_match = re.match(r'^n(\d+)$', parts[0])
    if not index_match:
        return None
    
    index = int(index_match.group(1))
    payload = '.'.join(parts[1:])
    
    return (index, payload)


def get_next_node_index(current_name: str, zone: str) -> Optional[int]:
    """
    Given an NSEC 'next name', extract what node index it represents.
    
    This is used to determine which payload chunk is revealed by an NSEC.
    
    Args:
        current_name: The 'next' field from an NSEC record
        zone: Zone name
        
    Returns:
        The node index, or None if not a valid node name
    """
    parsed = parse_node_name(current_name, zone)
    if parsed:
        return parsed[0]
    return None
