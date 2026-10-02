.PHONY: install create_script clean

install:
	@echo "Installing OpenAI module..."
	@pip3 install openai
	@pip3 install requests
	@pip3 install bs4
	@pip3 install python-dotenv
	@pip3 install directory_tree

# all_run.sh is maintained source, not a generated artifact.
create_script:
	@test -f all_run.sh || test -f goHelpers/all_run.sh || { echo "Restore the tracked all_run.sh from Git." >&2; exit 1; }
	@echo "Using maintained all_run.sh; no generation required."

clean:
	@echo "No generated wrapper artifacts to clean; all_run.sh is preserved."
