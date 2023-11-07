#!/bin/bash

# Check if an argument was provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

# The first argument is the directory to pass to the getter.py script
DIRECTORY=$1

# Call the getter.py script with the directory argument
python3 getter.py "$DIRECTORY"
