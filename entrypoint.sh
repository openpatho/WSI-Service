#!/bin/sh
# entrypoint.sh

# Check if the user already exists
if ! id -u appuser >/dev/null 2>&1; then
  # Create the user and group if they don't exist
  addgroup -g "$GID" appgroup || true
  adduser -u "$UID" -G appgroup -D -s /bin/sh appuser || true
fi

# Switch to the new user and execute the command
exec su-exec appuser "$@"
