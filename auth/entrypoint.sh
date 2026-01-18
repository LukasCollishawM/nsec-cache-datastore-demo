#!/bin/bash
set -e

echo "[*] NSEC Cache Datastore Demo - Authoritative Server"
echo "[*] ================================================"

# Configuration from environment
ZONE_NAME="${ZONE_NAME:-zone.test}"
TTL="${TTL:-60}"
MESSAGE="${MESSAGE:-hello from nsec cache datastore}"
CHUNK_SIZE="${CHUNK_SIZE:-8}"

ZONE_DIR="/var/cache/bind/zones"
KEY_DIR="/var/cache/bind/keys"
LOG_DIR="/var/log/named"

# Ensure directories exist and have correct permissions
mkdir -p "$ZONE_DIR" "$KEY_DIR" "$LOG_DIR"
chown -R bind:bind "$ZONE_DIR" "$KEY_DIR" "$LOG_DIR" /var/run/named

# Clear old query logs for clean demo runs
> "$LOG_DIR/query.log"
chown bind:bind "$LOG_DIR/query.log"

echo "[+] Generating zone file..."
python3 /generate_zone.py \
    --zone "$ZONE_NAME" \
    --message "$MESSAGE" \
    --chunk-size "$CHUNK_SIZE" \
    --ttl "$TTL" \
    --output "$ZONE_DIR/$ZONE_NAME.db"

echo "[+] Generating DNSSEC keys..."
cd "$KEY_DIR"

# Remove old keys if they exist
rm -f K${ZONE_NAME}.* 2>/dev/null || true

# Generate Key Signing Key (KSK)
echo "[+] Generating KSK..."
dnssec-keygen -a ECDSAP256SHA256 -f KSK -n ZONE "$ZONE_NAME" 2>/dev/null

# Generate Zone Signing Key (ZSK)
echo "[+] Generating ZSK..."
dnssec-keygen -a ECDSAP256SHA256 -n ZONE "$ZONE_NAME" 2>/dev/null

# List generated keys
echo "[+] Generated keys:"
ls -la K${ZONE_NAME}.*

# Copy keys to zone directory for signing
cp K${ZONE_NAME}.* "$ZONE_DIR/"

echo "[+] Signing zone with NSEC (not NSEC3)..."
cd "$ZONE_DIR"

# Sign the zone - NSEC is the default (no -3 flag)
# -A: include all signatures
# -N INCREMENT: use incrementing serial
# -o: origin
# -t: print stats
dnssec-signzone \
    -A \
    -N INCREMENT \
    -o "$ZONE_NAME" \
    -t \
    -K "$ZONE_DIR" \
    "$ZONE_NAME.db"

# The signed zone will be zone.test.db.signed
mv "$ZONE_NAME.db.signed" "$ZONE_NAME.signed"

echo "[+] Zone signed successfully"
echo "[+] Signed zone file: $ZONE_DIR/$ZONE_NAME.signed"

# Extract DNSKEY for recursor trust anchor
echo "[+] Extracting DNSKEY for trust anchor..."
grep "DNSKEY" "$ZONE_NAME.signed" | head -2 > "$KEY_DIR/trust-anchor.key"
cat "$KEY_DIR/trust-anchor.key"

# Also create a DS record format for reference
echo "[+] DS records (for reference):"
dnssec-dsfromkey -2 K${ZONE_NAME}*.key 2>/dev/null || true

# Set permissions
chown -R bind:bind "$ZONE_DIR" "$KEY_DIR"

echo "[+] Verifying zone..."
named-checkzone "$ZONE_NAME" "$ZONE_DIR/$ZONE_NAME.signed"

echo "[+] Starting BIND9 authoritative server..."
echo "[+] Query logging enabled at $LOG_DIR/query.log"

# Start named in foreground
exec /usr/sbin/named -g -c /etc/bind/named.conf -u bind
