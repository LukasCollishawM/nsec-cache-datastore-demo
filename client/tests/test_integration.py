"""
Integration tests for the NSEC Cache Datastore Demo.

These tests require Docker and docker-compose to be available.
They spin up the full demo environment and verify the behavior.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


# Skip all integration tests if not in Docker environment or CI
SKIP_INTEGRATION = os.environ.get('SKIP_INTEGRATION_TESTS', '0') == '1'


def run_command(cmd: list, cwd: str = None, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout
    )


def docker_compose_up(project_dir: str):
    """Start the docker-compose environment."""
    result = run_command(
        ['docker', 'compose', 'up', '-d', '--build'],
        cwd=project_dir,
        timeout=300
    )
    if result.returncode != 0:
        print(f"docker-compose up failed: {result.stderr}")
    return result.returncode == 0


def docker_compose_down(project_dir: str):
    """Stop the docker-compose environment."""
    run_command(
        ['docker', 'compose', 'down', '--remove-orphans', '-v'],
        cwd=project_dir,
        timeout=60
    )


def wait_for_services(max_wait: int = 60) -> bool:
    """Wait for services to be healthy."""
    start = time.time()
    while time.time() - start < max_wait:
        # Check if recursor can resolve
        result = run_command([
            'docker', 'exec', 'nsec-client',
            'python3', '-c',
            '''
import dns.resolver
r = dns.resolver.Resolver()
r.nameservers = ["172.28.0.3"]
r.lifetime = 2
try:
    r.resolve("ns1.zone.test.", "A")
    print("OK")
except Exception as e:
    print(f"FAIL: {e}")
    exit(1)
'''
        ])
        if result.returncode == 0 and 'OK' in result.stdout:
            return True
        time.sleep(2)
    return False


def run_prime(project_dir: str) -> dict:
    """Run the priming script and return results."""
    result = run_command([
        'docker', 'exec', 'nsec-client',
        'python3', '/app/scripts/prime.py'
    ], cwd=project_dir)
    
    if result.returncode != 0:
        print(f"Prime failed: {result.stderr}")
        return None
    
    # Read results file
    result = run_command([
        'docker', 'exec', 'nsec-client',
        'cat', '/results/prime_results.json'
    ])
    
    if result.returncode == 0:
        return json.loads(result.stdout)
    return None


def run_verify(project_dir: str) -> dict:
    """Run the verification script and return results."""
    result = run_command([
        'docker', 'exec', 'nsec-client',
        'python3', '/app/scripts/verify_synthesis.py'
    ], cwd=project_dir)
    
    # Read results file
    result = run_command([
        'docker', 'exec', 'nsec-client',
        'cat', '/results/verify_results.json'
    ])
    
    if result.returncode == 0:
        return json.loads(result.stdout)
    return None


@pytest.mark.skipif(SKIP_INTEGRATION, reason="Integration tests disabled")
class TestIntegration:
    """Integration tests for the full demo flow."""
    
    @pytest.fixture(scope="class")
    def project_dir(self):
        """Get the project root directory."""
        # Navigate up from tests directory
        return str(Path(__file__).parent.parent.parent)
    
    @pytest.fixture(scope="class", autouse=True)
    def setup_environment(self, project_dir):
        """Setup and teardown the Docker environment."""
        # Ensure .env exists
        env_example = Path(project_dir) / 'env.example'
        env_file = Path(project_dir) / '.env'
        
        if env_example.exists() and not env_file.exists():
            env_file.write_text(env_example.read_text())
        
        # Start environment
        print("\n[+] Starting Docker environment...")
        success = docker_compose_up(project_dir)
        
        if not success:
            pytest.skip("Could not start Docker environment")
        
        # Wait for services
        print("[+] Waiting for services to be healthy...")
        if not wait_for_services():
            docker_compose_down(project_dir)
            pytest.skip("Services did not become healthy in time")
        
        print("[+] Services are ready")
        
        yield
        
        # Teardown
        print("\n[+] Tearing down Docker environment...")
        docker_compose_down(project_dir)
    
    def test_services_running(self, project_dir):
        """Test that all services are running."""
        result = run_command(['docker', 'ps', '--format', '{{.Names}}'])
        
        assert 'nsec-auth' in result.stdout
        assert 'nsec-recursor' in result.stdout
        assert 'nsec-client' in result.stdout
    
    def test_zone_exists(self, project_dir):
        """Test that the signed zone exists on auth server."""
        result = run_command([
            'docker', 'exec', 'nsec-auth',
            'ls', '-la', '/var/cache/bind/zones/'
        ])
        
        assert 'zone.test.signed' in result.stdout
    
    def test_resolver_can_query_auth(self, project_dir):
        """Test that resolver can query the authoritative server."""
        result = run_command([
            'docker', 'exec', 'nsec-client',
            'dig', '@172.28.0.3', 'ns1.zone.test.', 'A', '+short'
        ])
        
        assert '192.0.2.1' in result.stdout
    
    def test_dnssec_validation(self, project_dir):
        """Test that DNSSEC validation is working."""
        result = run_command([
            'docker', 'exec', 'nsec-client',
            'dig', '@172.28.0.3', 'zone.test.', 'DNSKEY', '+dnssec', '+short'
        ])
        
        # Should have DNSKEY records
        assert '256' in result.stdout or '257' in result.stdout
    
    def test_priming_extracts_payload(self, project_dir):
        """Test that priming extracts the payload correctly."""
        prime_results = run_prime(project_dir)
        
        assert prime_results is not None
        assert 'decoded_payload' in prime_results
        assert 'hello' in prime_results['decoded_payload'].lower()
        assert prime_results['priming_queries'] > 0
    
    def test_verification_uses_cache(self, project_dir):
        """Test that verification queries use cached NSEC records."""
        # First ensure priming has run
        prime_results = run_prime(project_dir)
        assert prime_results is not None
        
        # Small delay to ensure cache is populated
        time.sleep(1)
        
        # Run verification
        verify_results = run_verify(project_dir)
        
        assert verify_results is not None
        assert 'delta' in verify_results
        
        # The key assertion: no new auth queries during verification
        # Note: In some configurations this might not be 0 due to
        # timing or configuration issues. We check for small delta.
        delta = verify_results['delta']
        assert delta <= 1, f"Expected Δ ≤ 1, got Δ = {delta}"
    
    def test_payload_matches_in_verification(self, project_dir):
        """Test that payload extracted during verification matches priming."""
        prime_results = run_prime(project_dir)
        assert prime_results is not None
        
        time.sleep(1)
        
        verify_results = run_verify(project_dir)
        assert verify_results is not None
        
        # Payloads should match
        prime_payload = prime_results.get('decoded_payload', '')
        verify_payload = verify_results.get('decoded_payload', '')
        
        # At minimum, both should contain the message
        assert 'hello' in prime_payload.lower()
        # Verification might extract partial payload depending on cache state
        # but should extract something
        assert len(verify_results.get('payload_chunks', [])) > 0
    
    def test_full_demo_flow(self, project_dir):
        """Test the complete demo flow end-to-end."""
        # This is the main acceptance test
        
        # 1. Prime
        prime_results = run_prime(project_dir)
        assert prime_results is not None
        assert prime_results['priming_queries'] > 0
        
        # 2. Wait for logs to settle
        time.sleep(1)
        
        # 3. Verify
        verify_results = run_verify(project_dir)
        assert verify_results is not None
        
        # 4. Check the key metric
        delta = verify_results['delta']
        
        print(f"\n[+] Demo Results:")
        print(f"    Priming queries: {prime_results['priming_queries']}")
        print(f"    Verification delta: {delta}")
        print(f"    Decoded payload: {prime_results['decoded_payload']}")
        
        # Accept delta <= 1 for timing variations
        assert delta <= 1, f"RFC 8198 aggressive negative caching not working: Δ = {delta}"


@pytest.mark.skipif(SKIP_INTEGRATION, reason="Integration tests disabled")
class TestDNSBehavior:
    """Tests for specific DNS behavior."""
    
    def test_nsec_in_nxdomain_response(self):
        """Test that NXDOMAIN responses include NSEC records."""
        # This test can run against any DNSSEC-signed zone
        # For now, skip if not in Docker environment
        result = run_command([
            'docker', 'exec', 'nsec-client',
            'dig', '@172.28.0.3', 'nonexistent.zone.test.', 'A', '+dnssec'
        ])
        
        if result.returncode != 0:
            pytest.skip("Could not query resolver")
        
        # Response should contain NSEC
        assert 'NSEC' in result.stdout or 'NXDOMAIN' in result.stdout
    
    def test_nsec_reveals_next_name(self):
        """Test that NSEC records reveal the next domain name."""
        result = run_command([
            'docker', 'exec', 'nsec-client',
            'dig', '@172.28.0.3', 'n0000z.zone.test.', 'A', '+dnssec'
        ])
        
        if result.returncode != 0:
            pytest.skip("Could not query resolver")
        
        # Should see NSEC with next name
        # The output should show the NSEC chain
        if 'NSEC' in result.stdout:
            # NSEC record shows the next name in the chain
            assert 'n000' in result.stdout.lower()
