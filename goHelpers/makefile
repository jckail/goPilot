.PHONY: install create_script clean

install:
	@echo "Installing OpenAI module..."
	@pip3 install openai
	@pip3 install requests
	@pip3 install bs4
	@pip3 install python-dotenv
	@pip3 install directory_tree

create_script:
	@echo "#!/bin/bash" > all_run.sh
	@echo "" >> all_run.sh
	@echo "# Check if one argument is given" >> all_run.sh
	@echo 'if [ "$$#" -ne 1 ]; then' >> all_run.sh
	@echo '    echo "Usage: $$0 <DIRECTORY>"' >> all_run.sh
	@echo '    exit 1' >> all_run.sh
	@echo 'fi' >> all_run.sh
	@echo "" >> all_run.sh
	@echo "# Hard-code the working directory to the current directory when this Makefile is run" >> all_run.sh
	@echo "WORKINGDIRECTORY=$(PWD)" >> all_run.sh
	@echo "" >> all_run.sh
	@echo "# Assign the argument to a variable" >> all_run.sh
	@echo 'DIRECTORY=$$1' >> all_run.sh
	@echo "" >> all_run.sh
	@echo "# Run the Python script with the two directories as arguments" >> all_run.sh
	@echo 'python3 "$$WORKINGDIRECTORY/main.py" "$$DIRECTORY" "$$WORKINGDIRECTORY" || echo "The python script failed to execute"' >> all_run.sh
	@chmod +x all_run.sh



clean:
	@rm -f all_run.sh
