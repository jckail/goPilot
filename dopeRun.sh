#!/bin/bash

# Default values for the arguments
DIRECTORY="."
UpdateContext=false
DeleteAll=false
RunCode=false
RunLint=false
RunTest=false
DeleteThreadsTxt=true
CodeOutput="${HOME}/projects/helpersPrivate/goHelpers/results/codeRun.txt"
LintOutput="${HOME}/projects/helpersPrivate/goHelpers/results/lintOutput.txt"
TestOutput="${HOME}/projects/helpersPrivate/goHelpers/results/testOutput.txt"


# Function to show usage
usage() {
    echo "Usage: $0 [-d DIRECTORY] [-u UpdateContext] [-a DeleteAll] [-r RunCode] [-n RunLint] [-t RunTest] [-c CodeOutput] [-l LintOutput] [-o TestOutput]"
    echo "  -d DIRECTORY     Specify the directory (default: current directory)"
    echo "  -u UpdateContext Specify UpdateContext (true/false, default: false)"
    echo "  -a DeleteAll     Specify DeleteAll (true/false, default: false)"
    echo "  -r RunCode       Specify RunCode (true/false, default: false)"
    echo "  -n RunLint       Specify RunLint (true/false, default: false)"
    echo "  -t RunTest       Specify RunTest (true/false, default: false)"
    echo "  -c CodeOutput    Specify CodeOutput (default: ${CodeOutput})"
    echo "  -l LintOutput    Specify LintOutput (default: ${LintOutput})"
    echo "  -o TestOutput    Specify TestOutput (default: ${TestOutput})"
    echo "  -x DeleteThreadsTxt    Specify DeleteThreadsTxt (true/false, default: true)"
    exit 1
}

# Parsing command-line options
while getopts ":d:u:a:r:n:t:c:l:o:" opt; do
  case $opt in
    d) DIRECTORY="$OPTARG"
       ;;
    u) UpdateContext="$OPTARG"
       ;;
    a) DeleteAll="$OPTARG"
       ;;
    r) RunCode="$OPTARG"
       ;;
    n) RunLint="$OPTARG"
       ;;
    t) RunTest="$OPTARG"
       ;;
    c) CodeOutput="$OPTARG"
       ;;
    l) LintOutput="$OPTARG"
       ;;
    o) TestOutput="$OPTARG"
       ;;
    x) DeleteThreadsTxt="$OPTARG"
       ;;
    \?) echo "Invalid option: -$OPTARG" >&2
        usage
        ;;
    :) echo "Option -$OPTARG requires an argument." >&2
       usage
       ;;
  esac
done

# Run the specified shell script
~/projects/helpersPrivate/goHelpers/all_run.sh -d "$DIRECTORY" -u "$UpdateContext" -a "$DeleteAll"

# Path to the file
FILE_PATH="${HOME}/projects/helpersPrivate/goHelpers/results/chatThreads.txt"
if [[ "$DeleteThreadsTxt" == "true" ]]; then
    # Check if the file exists
    if [ -f "$FILE_PATH" ]; then
        # Empty the file contents
        > "$FILE_PATH"
        echo "Contents of $FILE_PATH have been erased."
    else
        echo "File $FILE_PATH does not exist."
    fi
fi

# Conditional execution based on the flags
if [[ "$RunCode" == "true" ]]; then
  echo "Running code..."
  go run localtest/run/run.go > "$CodeOutput" 2>&1
  if ! python3 ~/projects/helpersPrivate/goHelpers/errorParser.py "$CodeOutput" >> "${HOME}/projects/helpersPrivate/goHelpers/results/chatThreads.txt"; then
      echo "errorParser failed to execute for CodeOutput" >&2
  fi
fi

if [[ "$RunLint" == "true" ]]; then
  echo "Running lints..."
  golangci-lint run --timeout=5m > "$LintOutput" 2>&1
  if ! python3 ~/projects/helpersPrivate/goHelpers/errorParser.py "$LintOutput" >> "${HOME}/projects/helpersPrivate/goHelpers/results/chatThreads.txt"; then
      echo "errorParser failed to execute for LintOutput" >&2
  fi
fi

if [[ "$RunTest" == "true" ]]; then
  echo "Running tests..." 
  go test ./... -coverprofile=coverage.txt -covermode count -timeout 2m > "$TestOutput" 2>&1
  if ! python3 ~/projects/helpersPrivate/goHelpers/errorParser.py "$TestOutput" >> "${HOME}/projects/helpersPrivate/goHelpers/results/chatThreads.txt"; then
      echo "errorParser failed to execute for TestOutput" >&2
  fi
fi

echo "Running Thread Parsers..."
  if ! python3 ~/projects/helpersPrivate/goHelpers/chatParse.py "${HOME}/projects/helpersPrivate/goHelpers/results/chatThreads.txt"; then
      echo "chatParse failed to execute for chatThreads" >&2
  fi
