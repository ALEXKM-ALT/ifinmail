# Postfix container for ifinmail
FROM ubuntu:24.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    postfix \
    postfix-pgsql \
    sasl2-bin \
    && rm -rf /var/lib/apt/lists/*

# Create vmail user (UID 5000, GID 5000 — must match dovecot)
RUN groupadd -g 5000 vmail \
    && useradd -g vmail -u 5000 -d /var/mail/vhosts -s /usr/sbin/nologin vmail

# Copy configuration
COPY main.cf /etc/postfix/main.cf.template
COPY master.cf /etc/postfix/master.cf
COPY pgsql/ /etc/postfix/pgsql-templates/
COPY entrypoint.sh /usr/local/bin/ifinmail-postfix-entrypoint

RUN mkdir -p /etc/postfix/pgsql \
    && chmod 640 /etc/postfix/pgsql-templates/*.cf \
    && chown root:postfix /etc/postfix/pgsql-templates/*.cf \
    && chmod +x /usr/local/bin/ifinmail-postfix-entrypoint \
    && mkdir -p /var/spool/postfix \
    && chown root:root /var/spool/postfix \
    && mkdir -p /var/mail/vhosts

EXPOSE 25 465 587

ENTRYPOINT ["ifinmail-postfix-entrypoint"]
CMD ["postfix", "start-fg"]
