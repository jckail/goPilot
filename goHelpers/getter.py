import os
import re
import logging

# Configure logging to write to stdout, which can be seen in the shell
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()


def consolidate_go_files(directory):
    # Dictionary to hold the package contents
    package_contents = {}

    # Dictionary to hold the unique imports for each package
    package_imports = {}

    # Regex to match package name and imports
    package_pattern = re.compile(r"^(?:\s*//.*\n)*\s*package (\S+)", re.MULTILINE)
    import_pattern = re.compile(r"^import (\S+)|import \(([\s\S]*?)\)")

    # Traverse through the directory
    for subdir, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".go") and not "_test" in file:
                logger.info(f"Processing file: {file}")
                file_path = os.path.join(subdir, file)

                with open(file_path, "r") as f:
                    contents = f.read()
                    if file == "gcr.go":
                        logger.info(
                            f"Contents of gcr.go before processing:\n{contents}"
                        )

                    # Find the package name
                    package_match = package_pattern.search(contents)
                    if package_match:
                        package_name = package_match.group(1)

                        # Initialize package contents and imports if not present
                        if package_name not in package_contents:
                            package_contents[package_name] = ""
                            package_imports[package_name] = set()

                        # Remove the package declaration from the content
                        contents = package_pattern.sub("", contents)

                        # Find and deduplicate imports
                        for match in import_pattern.finditer(contents):
                            if match.group(1):
                                # Single-line import
                                package_imports[package_name].add(
                                    match.group(1).strip("`")
                                )
                            elif match.group(2):
                                # Multi-line import block
                                import_block = match.group(2).strip()
                                imports = [
                                    imp.strip("`")
                                    for imp in import_block.split()
                                    if imp
                                ]
                                package_imports[package_name].update(imports)

                        # Remove imports from the content
                        contents = import_pattern.sub("", contents)

                        # Append the contents to the package contents
                        package_contents[package_name] += contents + "\n"

    # Now create the consolidated .txt files with imports and package declarations
    for package_name, contents in package_contents.items():
        # Prepend unique imports and the package name to the content
        unique_imports = "\n".join(sorted(package_imports[package_name]))
        final_content = (
            f"package {package_name}\n\nimport (\n{unique_imports}\n)\n\n{contents}"
        )

        # Write the final content to the file in the passed directory
        output_file_path = os.path.join(directory, f"{package_name}.txt")
        try:
            with open(output_file_path, "w") as f:
                f.write(final_content)
                logger.info(f"File written: {output_file_path}")
        except IOError as e:
            logger.error(f"Failed to write file: {output_file_path}, due to {e}")

    logger.info("Consolidation complete.")
    return "Consolidation complete."


# The directory to consolidate should be passed as a command-line argument
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        logger.error("Usage: python getter.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    consolidate_result = consolidate_go_files(directory)
    logger.info(consolidate_result)
