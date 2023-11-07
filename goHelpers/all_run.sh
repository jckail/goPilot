#!/bin/bash

# Script to run various Go-related commands


if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

# The first argument is the directory to pass to the getter.py script
DIRECTORY=$1

# Run the specified shell script
~/projects/helpersPrivate/goHelpers/run_getter.sh $DIRECTORY