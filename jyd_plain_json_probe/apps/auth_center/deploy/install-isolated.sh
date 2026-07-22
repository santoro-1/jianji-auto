#!/usr/bin/env bash
set -euo pipefail

archive=/tmp/jyd-auth-center-20260717.tar.gz
release=/opt/jyd-auth/releases/20260717-1

test -f "$archive"

if ! getent passwd jyd-auth >/dev/null; then
  useradd --system --home-dir /opt/jyd-auth --shell /sbin/nologin jyd-auth
fi

install -d -m 0755 /opt/jyd-auth /opt/jyd-auth/releases "$release"
install -d -o jyd-auth -g jyd-auth -m 0700 /opt/jyd-auth/data /opt/jyd-auth/config
tar -xzf "$archive" -C "$release"
chown -R root:root "$release"
chmod -R go-w "$release"

if [ ! -x /opt/jyd-auth/venv/bin/python ]; then
  python3 -m venv /opt/jyd-auth/venv
fi
/opt/jyd-auth/venv/bin/python -m pip install --disable-pip-version-check -r "$release/requirements.txt"

if [ ! -f /opt/jyd-auth/config/jyd-auth.env ]; then
  umask 077
  admin_password="$(openssl rand -base64 24 | tr -d '\n')"
  printf '%s\n' \
    'JYD_AUTH_DATA_DIR=/opt/jyd-auth/data' \
    'JYD_AUTH_ADMIN_USERNAME=admin' \
    "JYD_AUTH_ADMIN_PASSWORD=$admin_password" \
    'JYD_AUTH_COOKIE_SECURE=true' \
    'JYD_AUTH_SESSION_HOURS=12' \
    'JYD_AUTH_ALLOWED_HOSTS=auth.lanyingjk01.com,127.0.0.1,localhost' \
    > /opt/jyd-auth/config/jyd-auth.env
  chown jyd-auth:jyd-auth /opt/jyd-auth/config/jyd-auth.env
fi

ln -sfn "$release" /opt/jyd-auth/current
install -o root -g root -m 0644 /tmp/jyd-auth.service /etc/systemd/system/jyd-auth.service
systemctl daemon-reload
systemctl enable --now jyd-auth.service
