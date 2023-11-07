#!/bin/bash

# This script runs the getter.py script with a provided directory

# Echo the current directory
echo "Current directory: $(pwd)"

# Get the full path to the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
echo "Script directory: $SCRIPT_DIR"

# Check if an argument was provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

# The first argument is the directory to pass to the getter.py script
DIRECTORY=$1

# Echo the command about to run
echo "Running command: python3 \"$SCRIPT_DIR/main.py\" \"$DIRECTORY\""

# Call the getter.py script with the directory argument
python3 "$SCRIPT_DIR/main.py" "$DIRECTORY" || echo "The python script failed to execute"
