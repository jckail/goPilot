#!/bin/bash

usage() {
    printf 'Usage: %s <URL>\n' "$0"
}

if [[ "$#" -ne 1 ]]; then
    usage >&2
    exit 1
fi

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    usage
    exit 0
fi

if [[ ! "$1" =~ [^[:space:]] ]]; then
    usage >&2
    exit 1
fi

# Resolve the adjacent helper without changing the caller's working directory.
HELPER_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd) || exit 1
exec python3 "$HELPER_DIRECTORY/htmlParser.py" "$1" "$HELPER_DIRECTORY"
