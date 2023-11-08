#!/bin/bash

# Default values for the arguments
DIRECTORY="."
UpdateContext=false
DeleteAll=false

# Function to show usage
usage() {
    echo "Usage: $0 [-d DIRECTORY] [-u UpdateContext] [-a DeleteAll]"
    echo "  -d DIRECTORY     Specify the directory (default: current directory)"
    echo "  -u UpdateContext Specify UpdateContext (true/false, default: false)"
    echo "  -a DeleteAll     Specify DeleteAll (true/false, default: false)"
    exit 1
}

# Parsing command-line options
while getopts ":d:u:a:" opt; do
  case $opt in
    d) DIRECTORY="$OPTARG"
       ;;
    u) UpdateContext="$OPTARG"
       if [ "$UpdateContext" != "true" ] && [ "$UpdateContext" != "false" ]; then
           echo "UpdateContext must be a boolean value: true or false"
           exit 2
       fi
       ;;
    a) DeleteAll="$OPTARG"
       if [ "$DeleteAll" != "true" ] && [ "$DeleteAll" != "false" ]; then
           echo "DeleteAll must be a boolean value: true or false"
           exit 2
       fi
       ;;
    \?) echo "Invalid option: -$OPTARG" >&2
        usage
        ;;
    :) echo "Option -$OPTARG requires an argument." >&2
       usage
       ;;
  esac
done

# Hard-code the working directory to the current directory when this Makefile is run
WORKINGDIRECTORY=/home/ec2-user/projects/helpersPrivate/goHelpers

# Run the Python script with the two directories as arguments and the booleans
python3 "$WORKINGDIRECTORY/main.py" "$DIRECTORY" "$WORKINGDIRECTORY" "$UpdateContext" "$DeleteAll" || echo "The python script failed to execute"
