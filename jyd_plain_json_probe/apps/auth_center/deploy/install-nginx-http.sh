#!/usr/bin/env bash
set -euo pipefail

install -d -o root -g root -m 0755 /opt/jyd-auth/acme
install -o root -g root -m 0644 /tmp/jyd-auth-http.conf /etc/nginx/conf.d/jyd-auth.conf

if nginx -t; then
  systemctl reload nginx
else
  mv /etc/nginx/conf.d/jyd-auth.conf /opt/jyd-auth/jyd-auth.conf.failed
  nginx -t
  exit 1
fi
