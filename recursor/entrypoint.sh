#!/bin/bash
set -e

echo "[*] NSEC Cache Datastore Demo - Recursive Resolver"
echo "[*] ==============================================="

AUTH_IP="${AUTH_IP:-172.28.0.2}"
LOG_DIR="/var/log/unbound"
KEY_DIR="/keys"

# Ensure directories exist
mkdir -p "$LOG_DIR" /var/lib/unbound /var/run
chown -R unbound:unbound "$LOG_DIR" /var/lib/unbound

# Clear old logs for clean demo runs
> "$LOG_DIR/unbound.log"
chown unbound:unbound "$LOG_DIR/unbound.log"

echo "[+] Waiting for authoritative server trust anchor..."

# Wait for trust anchor file from auth container
MAX_WAIT=60
WAITED=0
while [ ! -f "$KEY_DIR/trust-anchor.key" ] || [ ! -s "$KEY_DIR/trust-anchor.key" ]; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "[-] Timeout waiting for trust anchor"
        exit 1
    fi
    echo "[.] Waiting for trust anchor... ($WAITED/$MAX_WAIT)"
    sleep 2
    WAITED=$((WAITED + 2))
done

echo "[+] Trust anchor found"

# Create trust anchor configuration for Unbound
# Extract the DNSKEY records and format them for Unbound
echo "[+] Configuring trust anchor..."

# Create a trust anchor file in Unbound format
# Format: zone. IN DNSKEY flags proto algo key
TRUST_ANCHOR_FILE="/var/lib/unbound/zone.test.key"

# Copy the DNSKEY records
cp "$KEY_DIR/trust-anchor.key" "$TRUST_ANCHOR_FILE"
chown unbound:unbound "$TRUST_ANCHOR_FILE"

echo "[+] Trust anchor content:"
cat "$TRUST_ANCHOR_FILE"

# Create an additional config file for the trust anchor
cat > /etc/unbound/unbound.conf.d/trust-anchor.conf << EOF
server:
    trust-anchor-file: "$TRUST_ANCHOR_FILE"
EOF

# Verify configuration
echo "[+] Verifying Unbound configuration..."
unbound-checkconf /etc/unbound/unbound.conf

echo "[+] RFC 8198 Aggressive NSEC caching: ENABLED"
echo "[+] Forward zone.test. -> $AUTH_IP"
echo "[+] Logging to $LOG_DIR/unbound.log"

echo "[+] Starting Unbound recursive resolver..."

# Start unbound in foreground
exec /usr/sbin/unbound -d -c /etc/unbound/unbound.conf
