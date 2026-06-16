FROM alpine:3.21

RUN apk add --no-cache postfix postfix-pgsql musl-locales

COPY conf/main.cf /etc/postfix/main.cf
COPY conf/master.cf /etc/postfix/master.cf
COPY conf/pgsql/ /etc/postfix/pgsql/
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 25 587

ENTRYPOINT ["/entrypoint.sh"]
CMD ["postfix", "start-fg"]
