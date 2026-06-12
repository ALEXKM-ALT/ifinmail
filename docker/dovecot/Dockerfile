FROM dovecot/dovecot:2.4-ubuntu

RUN apt-get update && apt-get install -y --no-install-recommends \
    dovecot-pgsql \
    dovecot-lmtpd \
    dovecot-sieve \
    && rm -rf /var/lib/apt/lists/*

COPY conf/dovecot.conf /etc/dovecot/dovecot.conf
COPY conf/conf.d/ /etc/dovecot/conf.d/
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && mkdir -p /var/mail /etc/dovecot/private \
    && groupadd -g 5000 vmail || true \
    && useradd -g vmail -u 5000 vmail -d /var/mail || true \
    && chown -R vmail:vmail /var/mail || true

EXPOSE 143 993 24 12345

ENTRYPOINT ["/entrypoint.sh"]
