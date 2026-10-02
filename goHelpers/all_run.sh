#!/bin/bash

DIRECTORY="."
UpdateContext=false
DeleteAll=false

usage() {
    echo "Usage: $0 [-d DIRECTORY] [-u true|false] [-a true|false] [-h|--help]"
    echo "Runs the provider-aware helper. All flags false is not a dry run."
}
fail() { echo "$1" >&2; usage >&2; exit 2; }

while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        -d|-u|-a)
            option="$1"
            [ "$#" -ge 2 ] && [ -n "$2" ] && [[ "$2" != -* ]] || fail "Option $option requires an argument."
            case "$option" in
                -d) DIRECTORY="$2" ;;
                -u|-a)
                    [[ "$2" == true || "$2" == false ]] || fail "Option $option must be true or false."
                    if [ "$option" == -u ]; then UpdateContext="$2"; else DeleteAll="$2"; fi
                    ;;
            esac
            shift 2 ;;
        --) shift; [ "$#" -eq 0 ] || fail "Unexpected positional argument: $1" ;;
        *) fail "Unknown option or positional argument: $1" ;;
    esac
done

[ -d "$DIRECTORY" ] || fail "Context directory must exist and be a directory: $DIRECTORY"

WORKINGDIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
mkdir -p -- "$WORKINGDIRECTORY/results" || exit "$?"
python3 "$WORKINGDIRECTORY/main.py" "$DIRECTORY" "$WORKINGDIRECTORY" "$UpdateContext" "$DeleteAll"
status=$?
if [ "$status" -ne 0 ]; then echo "The Python helper failed (exit $status)." >&2; fi
exit "$status"
