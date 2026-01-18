FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Unbound and tools
RUN apt-get update && apt-get install -y \
    unbound \
    unbound-host \
    dnsutils \
    ldnsutils \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /var/log/unbound /var/lib/unbound /etc/unbound/unbound.conf.d \
    && chown -R unbound:unbound /var/log/unbound /var/lib/unbound

# Copy configuration
COPY entrypoint.sh /entrypoint.sh
COPY unbound.conf /etc/unbound/unbound.conf

RUN chmod +x /entrypoint.sh

EXPOSE 53/udp 53/tcp

ENTRYPOINT ["/entrypoint.sh"]
