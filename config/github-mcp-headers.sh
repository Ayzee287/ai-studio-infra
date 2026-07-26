#!/usr/bin/env bash
# Emits the Authorization header for the GitHub MCP server, at connect time.
#
# Why this exists: Claude Code cannot OAuth against api.githubcopilot.com (that auth
# server does not support RFC 7591 dynamic client registration), and we refuse to
# write a personal access token into ~/.claude.json. So no token is stored by us at
# all: it is read from the OS credential store on every connection.
#
# Resolution order (first hit wins):
#   1. $GITHUB_PERSONAL_ACCESS_TOKEN   explicit override (CI, or a scoped PAT)
#   2. gh auth token                   GitHub CLI's own secure store
#   3. git credential fill             Git Credential Manager
#
# Contract: print ONE JSON object of string key/value pairs on stdout and nothing
# else; stray output corrupts the header set. Exit 0 with {} when no credential is
# found, so the server reports unauthenticated instead of breaking session startup.
# The token is never echoed, logged, or written to disk.

set -u
token=""

if [ -n "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]; then
  token="$GITHUB_PERSONAL_ACCESS_TOKEN"
fi

if [ -z "$token" ]; then
  for ghbin in gh "/c/Program Files/GitHub CLI/gh.exe"; do
    if command -v "$ghbin" >/dev/null 2>&1 || [ -x "$ghbin" ]; then
      t="$("$ghbin" auth token 2>/dev/null || true)"
      if [ -n "$t" ]; then token="$t"; break; fi
    fi
  done
fi

if [ -z "$token" ]; then
  token="$(printf 'protocol=https\nhost=github.com\n\n' \
    | git credential fill 2>/dev/null \
    | sed -n 's/^password=//p' | tr -d '\r\n' || true)"
fi

if [ -n "$token" ]; then
  printf '{"Authorization":"Bearer %s"}\n' "$token"
else
  printf '{}\n'
fi
