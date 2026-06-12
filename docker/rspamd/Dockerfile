FROM rspamd/rspamd:latest

COPY conf/local.d/ /etc/rspamd/local.d/
COPY conf/override.d/ /etc/rspamd/override.d/

RUN mkdir -p /var/lib/rspamd/dkim \
    && chown -R _rspamd:_rspamd /var/lib/rspamd

EXPOSE 11332 11333 11334

CMD ["rspamd", "-f", "-u", "_rspamd", "-g", "_rspamd"]
