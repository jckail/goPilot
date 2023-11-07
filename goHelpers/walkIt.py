import os
import logging

# Configure logging to write to stdout, which can be seen in the shell
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()


def list_directories(path):
    # List to hold all directories
    directories = []

    # Walk through the directory
    for root, dirs, files in os.walk(path):
        # Edit the dirs in place to skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for directory in dirs:
            directories.append(os.path.join(root, directory))
    return directories


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        logger.error("Usage: python getter.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    consolidate_result = list_directories(directory)
    logger.info(consolidate_result)
