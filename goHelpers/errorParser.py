import addGo
import sys
import os
import logging
# Configure logging to write to stdout, which can be seen in the shell
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()

def main(file_path):
    print(f"trying: {file_path}")
    error_keywords = ["Failed", "Error", "ExpiredToken", "status code: 400",".go"]  # Add more keywords as needed
    errors = []
    with open(file_path, 'r') as file:
        for line in file:
            if any(keyword in line for keyword in error_keywords):
                errors.append(line.strip())
    print(errors)
    return errors

if __name__ == "__main__":

    if len(sys.argv) != 2:
        logger.error("Usage: python errorParser.py <directory>")
        sys.exit(1)

    file_path = str(sys.argv[1])
    logger.info("%s", file_path)
    print("file_path: ",file_path)

    #goHelperDirectory = "/home/ec2-user/projects/goHelper/goHelpers/"
    # file_path = goHelperDirectory + "results/results.txt"
    addContent = main(file_path)
    helper_directory = os.path.dirname(os.path.abspath(__file__)) + os.sep
    aM = addGo.AssistantManager("goBot", helper_directory)
    aM.createThread(addContent)