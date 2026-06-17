#!/usr/bin/env sh
# Sets host uid/gid for .:/app bind-mount permissions, then runs docker compose.
export DOCKER_UID=$(id -u)
export DOCKER_GID=$(id -g)
exec docker compose "$@"
