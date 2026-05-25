# Rspamd container for ifinmail
FROM ubuntu:24.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    rspamd \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Create Rspamd directories
RUN mkdir -p /var/lib/rspamd /var/log/rspamd /etc/dkim

# Copy local configuration overrides
COPY local.d/ /etc/rspamd/local.d/

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 11332 11333 11334

ENTRYPOINT ["/entrypoint.sh"]
