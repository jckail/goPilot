import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()


def parse_and_save_unique_threads(file_path):
    # Set to store unique lines
    unique_lines = set()
    
    # Read the file content
    with open(file_path, 'r') as file:
        for line in file:
            if "View response here:" in line:
                unique_lines.add(line.strip())

    # Print unique lines to standard out
    for line in unique_lines:
        print(line)

    #print(file_path)
    basefile = os.path.basename(file_path)
    file_path = file_path.replace(basefile, "unique_" + basefile)
    #print(file_path)
    # Save unique lines to a new file
    with open(file_path, 'w') as output_file:
        for line in unique_lines:
            output_file.write(line + '\n')


if __name__ == "__main__":

    if len(sys.argv) != 2:
        logger.error("Usage: python errorParser.py <directory>")
        sys.exit(1)

    file_path = str(sys.argv[1])
    logger.info("%s", file_path)
    # print("file_path: ",file_path)

    #goHelperDirectory = "/home/ec2-user/projects/helpersPrivate/goHelpers/"
    # file_path = goHelperDirectory + "results/results.txt"
    #aM = addGo.AssistantManager( "goBot", file_path)
    # file_path = "/home/ec2-user/projects/helpersPrivate/goHelpers/results/"
    # inputName = "chatThreads.txt"
    # outputName = "uniqueChatThreads.txt"
    # p = "/home/ec2-user/projects/helpersPrivate/goHelpers/results/chatThreads.txt"
    addContent = parse_and_save_unique_threads(file_path)
    