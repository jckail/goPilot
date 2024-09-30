# goPilot CLI Tool

This CLI tool is designed to facilitate various operations such as updating context, deleting files, running code, linting, and testing within the Go development environment. It also provides the ability to control output locations for code execution, linting, and test results.

## Prerequisites

Before using the CLI, ensure you have the following installed:

- Tweak `localtest/run.sh` so that it runs i with your runners.
- Python 3 with `errorParser.py` and `chatParse.py` scripts located at `~/projects/goHelper/goHelpers/`
- Golang with `golangci-lint` and `go test` tools installed
- Run `export OPENAI_API_KEY="your_api_key"`

## Usage

Execute the CLI script with the desired options:

### Most Commonly used updates contexts, runs code, runs lint, runs tests:
```./localtest/run.sh -u true -r true -n true -t true```

### Run the script with a specified directory and enable code running:
```./cli_script.sh -d ~/myGoProject -r true```

### Run the script to update the context, run linter, and run tests in a specific directory:
```./cli_script.sh -d ~/myGoProject -u true -n true -t true```

### Specify custom output paths for the execution, linting, and testing results:
```./cli_script.sh -c ~/custom/path/code.txt -l ~/custom/path/lint.txt -o ~/custom/path/test.txt```

### Run the script to delete all threads text and run tests without linting or running code:
```./cli_script.sh -a true -t true -n false -r false```

## Options
`./cli_script.sh [options]`
`If an invalid option is passed, the script will display a usage message and exit.`

- `-d DIRECTORY`: Specify the directory to work in (default: current directory).
- `-u`: Update context (set to `true` or `false`, default: `false`).
- `-a`: Delete all threads text (set to `true` or `false`, default: `false`).
- `-r`: Run code (set to `true` or `false`, default: `false`).
- `-n`: Run linter (set to `true` or `false`, default: `false`).
- `-t`: Run tests (set to `true` or `false`, default: `false`).
- `-c`: Path for code execution output (default: `~/projects/goHelper/goHelpers/results/codeRun.txt`).
- `-l`: Path for linting output (default: `~/projects/goHelper/goHelpers/results/lintOutput.txt`).
- `-o`: Path for testing output (default: `~/projects/goHelper/goHelpers/results/testOutput.txt`).
- `-x`: Delete the threads text file after execution (set to `true` or `false`, default: `true`).



