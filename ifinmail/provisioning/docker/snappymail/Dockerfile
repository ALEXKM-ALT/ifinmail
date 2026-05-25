FROM php:8.3-fpm-alpine

RUN apk add --no-cache \
    curl \
    unzip \
    nginx \
    supervisor \
    icu-libs \
    libxml2 \
    libsodium \
    && apk add --no-cache --virtual .build-deps \
    icu-dev \
    libxml2-dev \
    $PHPIZE_DEPS \
    && docker-php-ext-install -j "$(nproc)" \
    intl \
    xml \
    sodium \
    sodium \
    && apk del .build-deps \
    && rm -rf /var/cache/apk/*

ENV SNAPPYMAIL_VERSION=2.38.0

RUN mkdir -p /var/www/snappymail /var/lib/snappymail && \
    curl -fsSL "https://github.com/the-djmaze/snappymail/releases/download/v${SNAPPYMAIL_VERSION}/snappymail-${SNAPPYMAIL_VERSION}.zip" \
    -o /tmp/snappymail.zip && \
    unzip -q /tmp/snappymail.zip -d /var/www/snappymail && \
    rm /tmp/snappymail.zip && \
    chown -R www-data:www-data /var/www/snappymail /var/lib/snappymail

COPY nginx-snappymail.conf /etc/nginx/http.d/snappymail.conf
COPY supervisord.conf /etc/supervisord.conf

RUN rm -f /etc/nginx/http.d/default.conf

EXPOSE 8888

CMD ["supervisord", "-c", "/etc/supervisord.conf"]
