"""
DNS Response Parser for NSEC Records

Provides utilities for extracting NSEC records and their 'next name'
fields from DNS responses using dnspython.
"""

from typing import List, Optional, Tuple
import dns.message
import dns.name
import dns.rdata
import dns.rdatatype
import dns.rrset
import dns.resolver


def extract_nsec_from_response(response: dns.message.Message) -> List[dns.rrset.RRset]:
    """
    Extract all NSEC RRsets from a DNS response.
    
    NSEC records appear in the authority section of NXDOMAIN responses.
    
    Args:
        response: A dnspython Message object
        
    Returns:
        List of NSEC RRsets found in the authority section
    """
    nsec_rrsets = []
    
    # Check authority section (where NSEC records appear for NXDOMAIN)
    for rrset in response.authority:
        if rrset.rdtype == dns.rdatatype.NSEC:
            nsec_rrsets.append(rrset)
    
    # Also check answer section (for positive NSEC responses)
    for rrset in response.answer:
        if rrset.rdtype == dns.rdatatype.NSEC:
            nsec_rrsets.append(rrset)
    
    return nsec_rrsets


def extract_next_name(nsec_rrset: dns.rrset.RRset) -> Optional[dns.name.Name]:
    """
    Extract the 'next domain name' from an NSEC RRset.
    
    The NSEC record format is:
        owner_name TTL NSEC next_domain_name [type_bit_maps]
    
    The 'next' field reveals the next name in the zone's sorted order,
    which is how we extract the payload.
    
    Args:
        nsec_rrset: An NSEC RRset
        
    Returns:
        The next domain name, or None if no NSEC rdata
    """
    for rdata in nsec_rrset:
        # NSEC rdata has a 'next' attribute
        if hasattr(rdata, 'next'):
            return rdata.next
    return None


def extract_payload_from_next_name(
    next_name: dns.name.Name,
    zone: str
) -> Optional[str]:
    """
    Extract the encoded payload labels from an NSEC next name.
    
    Given a next name like 'n0001.nbswy3dp.zone.test.', extract 'nbswy3dp'.
    
    Args:
        next_name: The dns.name.Name object from NSEC next field
        zone: The zone name
        
    Returns:
        The encoded payload labels, or None if format doesn't match
    """
    # Convert to string
    name_str = next_name.to_text().lower()
    zone = zone.lower().rstrip('.')
    
    # Check if it ends with our zone
    if not name_str.rstrip('.').endswith(zone):
        return None
    
    # Remove zone suffix
    prefix = name_str.rstrip('.')
    zone_suffix = '.' + zone
    if prefix.endswith(zone_suffix):
        prefix = prefix[:-len(zone_suffix)]
    
    # Split into labels
    labels = prefix.split('.')
    
    # First label should be nXXXX
    if not labels or not labels[0].startswith('n'):
        return None
    
    # Remaining labels are the payload
    if len(labels) < 2:
        return None
    
    payload_labels = '.'.join(labels[1:])
    return payload_labels


def query_and_extract_nsec(
    name: str,
    resolver_ip: str,
    timeout: float = 5.0
) -> Tuple[Optional[dns.name.Name], Optional[dns.message.Message]]:
    """
    Query a name and extract the NSEC next-name from the response.
    
    This is the main function used during priming/verification.
    
    Args:
        name: The name to query (should be an in-gap name)
        resolver_ip: IP address of the resolver
        timeout: Query timeout in seconds
        
    Returns:
        Tuple of (next_name, full_response) or (None, response) on failure
    """
    resolver = dns.resolver.Resolver()
    resolver.nameservers = [resolver_ip]
    resolver.timeout = timeout
    resolver.lifetime = timeout
    
    # We want DNSSEC data
    resolver.use_edns(edns=0, ednsflags=dns.flags.DO, payload=4096)
    
    try:
        # This will raise NXDOMAIN which we catch
        resolver.resolve(name, 'A')
        # If we get here, the name exists (unexpected)
        return (None, None)
    except dns.resolver.NXDOMAIN as e:
        # This is expected - we want the NSEC from the NXDOMAIN response
        response = e.response()
        
        # Extract NSEC
        nsec_rrsets = extract_nsec_from_response(response)
        
        for nsec_rrset in nsec_rrsets:
            next_name = extract_next_name(nsec_rrset)
            if next_name:
                return (next_name, response)
        
        return (None, response)
    except dns.resolver.NoAnswer as e:
        return (None, e.response())
    except Exception as e:
        print(f"[!] Query error for {name}: {e}")
        return (None, None)


def get_nsec_proof_info(
    response: dns.message.Message,
    zone: str
) -> List[dict]:
    """
    Extract detailed NSEC proof information from a response.
    
    Args:
        response: DNS response message
        zone: Zone name
        
    Returns:
        List of dicts with NSEC proof details
    """
    proofs = []
    nsec_rrsets = extract_nsec_from_response(response)
    
    for rrset in nsec_rrsets:
        owner = rrset.name.to_text()
        next_name = extract_next_name(rrset)
        
        if next_name:
            payload = extract_payload_from_next_name(next_name, zone)
            proofs.append({
                'owner': owner,
                'next': next_name.to_text(),
                'payload': payload,
                'ttl': rrset.ttl
            })
    
    return proofs
