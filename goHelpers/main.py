import openai
import os
import logging
import walkIt
import addGo
import getter
import sys
import shutil

# Configure logging to write to stdout, which can be seen in the shell
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()



def copy_file(source, destination):
    try:
        # Copy the source file to the destination path
        shutil.copy(source, destination)
        print(f"File {source} copied to {destination} successfully.")
    except FileNotFoundError:
        print("The source file does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    apiKey = "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"
    model = "gpt-4-1106-preview"
    file_path = "/Users/jkail/projects/databus/gcr/"
    file_name = "gcr.txt"
    uploadFile = file_path + file_name

    if len(sys.argv) != 2:
        logger.error("Usage: python getter.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    directories = walkIt.list_directories(directory)
    logger.info(directories)
    files = getter.consolidate_go_files(directory)
    logger.info(files)
    # files.append("/Users/jkail/projects/helpersPrivate/goHelpers/best_practices_context.txt")
    # files.append("/home/ec2-user/projects/helpersPrivate/goHelpers/best_practices_context.txt")
    # assistantId = "asst_6Jqvv49JQCXZrTLMnSBb8xNM"
    assistantManager = addGo.AssistantManager(apiKey, "goBot")
    # assistantManager.removeFilesFromAssistant()
    # assistantManager.deleteAllFiles()
    assistantManager.uploadFilestoAssistant(files)
