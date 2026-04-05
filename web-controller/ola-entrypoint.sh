#!/bin/bash
# Fix ownership of the config bind-mount (may be created by Docker as root),
# then drop to the ola user.
chown -R ola:ola /etc/ola
exec runuser -u ola -- "$@"
