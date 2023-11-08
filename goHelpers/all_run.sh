#!/bin/bash

# Check if one argument is given
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <DIRECTORY>"
    exit 1
fi

# Hard-code the working directory to the current directory when this Makefile is run
WORKINGDIRECTORY=/home/ec2-user/projects/helpersPrivate/goHelpers

# Assign the argument to a variable
DIRECTORY=$1

# Run the Python script with the two directories as arguments
python3 "$WORKINGDIRECTORY/main.py" "$DIRECTORY" "$WORKINGDIRECTORY" || echo "The python script failed to execute"
