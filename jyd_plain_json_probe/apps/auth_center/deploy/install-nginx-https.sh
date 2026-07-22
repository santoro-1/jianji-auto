#!/usr/bin/env bash
set -euo pipefail

install -o root -g root -m 0644 /etc/nginx/conf.d/jyd-auth.conf /opt/jyd-auth/jyd-auth-http.backup.conf
install -o root -g root -m 0644 /tmp/jyd-auth-https.conf /etc/nginx/conf.d/jyd-auth.conf

if nginx -t; then
  systemctl reload nginx
else
  install -o root -g root -m 0644 /opt/jyd-auth/jyd-auth-http.backup.conf /etc/nginx/conf.d/jyd-auth.conf
  nginx -t
  exit 1
fi
