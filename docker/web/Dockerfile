# Apache + PHP avec extensions MySQL — images officielles multi-arch (amd64 + arm64 / Raspberry Pi).
FROM php:8.2-apache

RUN docker-php-ext-install mysqli pdo pdo_mysql \
    && a2enmod rewrite
