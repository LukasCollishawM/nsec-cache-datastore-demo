FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install BIND9 and tools
RUN apt-get update && apt-get install -y \
    bind9 \
    bind9utils \
    bind9-dnsutils \
    dnsutils \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /var/cache/bind/zones \
    /var/cache/bind/keys \
    /var/log/named \
    /var/run/named \
    && chown -R bind:bind /var/cache/bind /var/log/named /var/run/named

# Copy configuration files
COPY named.conf /etc/bind/named.conf
COPY entrypoint.sh /entrypoint.sh
COPY generate_zone.py /generate_zone.py

RUN chmod +x /entrypoint.sh /generate_zone.py

EXPOSE 53/udp 53/tcp

ENTRYPOINT ["/entrypoint.sh"]
