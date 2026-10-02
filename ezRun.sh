#!/bin/bash

DIRECTORY="."
UpdateContext=false
DeleteAll=false
RunCode=false
RunLint=false
RunTest=false
DeleteThreadsTxt=true
CodeOutput=""
LintOutput=""
TestOutput=""

usage() {
    echo "Usage: $0 [-d DIRECTORY] [-u true|false] [-a true|false] [-r true|false] [-n true|false] [-t true|false] [-x true|false] [-c FILE] [-l FILE] [-o FILE] [-h|--help]"
    echo "  -d selects context; Go commands retain the caller's working directory."
    echo "  -c/-l/-o select code/lint/test output (default: this checkout's goHelpers/results)."
    echo "  -x controls thread-log cleanup (default: true, after helper success)."
    echo "All flags false still runs the provider-aware helper; this is not a dry run."
}
fail() { echo "$1" >&2; usage >&2; exit 2; }

while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        -d|-u|-a|-r|-n|-t|-x|-c|-l|-o)
            option="$1"
            [ "$#" -ge 2 ] && [ -n "$2" ] && [[ "$2" != -* ]] || fail "Option $option requires an argument."
            case "$option" in
                -d) DIRECTORY="$2" ;;
                -c) CodeOutput="$2" ;;
                -l) LintOutput="$2" ;;
                -o) TestOutput="$2" ;;
                *)
                    [[ "$2" == true || "$2" == false ]] || fail "Option $option must be true or false."
                    case "$option" in
                        -u) UpdateContext="$2" ;;
                        -a) DeleteAll="$2" ;;
                        -r) RunCode="$2" ;;
                        -n) RunLint="$2" ;;
                        -t) RunTest="$2" ;;
                        -x) DeleteThreadsTxt="$2" ;;
                    esac ;;
            esac
            shift 2 ;;
        --) shift; [ "$#" -eq 0 ] || fail "Unexpected positional argument: $1" ;;
        *) fail "Unknown option or positional argument: $1" ;;
    esac
done

[ -d "$DIRECTORY" ] || fail "Context directory must exist and be a directory: $DIRECTORY"

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
HELPER_DIRECTORY="$SCRIPT_DIRECTORY/goHelpers"
RESULTS_DIRECTORY="$HELPER_DIRECTORY/results"
CodeOutput="${CodeOutput:-$RESULTS_DIRECTORY/codeRun.txt}"
LintOutput="${LintOutput:-$RESULTS_DIRECTORY/lintOutput.txt}"
TestOutput="${TestOutput:-$RESULTS_DIRECTORY/testOutput.txt}"

bash "$HELPER_DIRECTORY/all_run.sh" -d "$DIRECTORY" -u "$UpdateContext" -a "$DeleteAll"
status=$?
[ "$status" -eq 0 ] || exit "$status"

# Only touch the selected checkout's thread log after successful helper work.
FILE_PATH="$RESULTS_DIRECTORY/chatThreads.txt"
if [ "$DeleteThreadsTxt" == true ]; then
    : > "$FILE_PATH" || exit "$?"
else
    if [ ! -e "$FILE_PATH" ]; then : > "$FILE_PATH" || exit "$?"; fi
fi

parse_errors() {
    python3 "$HELPER_DIRECTORY/errorParser.py" "$1" >> "$FILE_PATH"
}

# A failed Go check still needs its diagnostics routed through the parser.
if [ "$RunCode" == true ]; then
    go run localtest/run/run.go > "$CodeOutput" 2>&1
    parse_errors "$CodeOutput" || exit "$?"
fi
if [ "$RunLint" == true ]; then
    golangci-lint run --timeout=5m > "$LintOutput" 2>&1
    parse_errors "$LintOutput" || exit "$?"
fi
if [ "$RunTest" == true ]; then
    go test ./... -coverprofile=coverage.txt -covermode count -timeout 2m > "$TestOutput" 2>&1
    parse_errors "$TestOutput" || exit "$?"
fi

python3 "$HELPER_DIRECTORY/chatParse.py" "$FILE_PATH"
exit "$?"
