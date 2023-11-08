import openai
import os
import logging
import walkIt
import addGo
import getter
import sys
import shutil
import htmlParser

# Configure logging to write to stdout, which can be seen in the shell
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()

webreources = [
            "https://pkg.go.dev/os",
            "https://pkg.go.dev/github.com/twmb/franz-go/pkg/kgo",
               "https://pkg.go.dev/github.com/xeipuuv/gojsonschema", 
               "https://pkg.go.dev/github.com/hamba/avro/v2",
               "https://pkg.go.dev/github.com/aws/aws-sdk-go/aws",
               "https://pkg.go.dev/github.com/aws/aws-sdk-go/service/s3",
               "https://pkg.go.dev/encoding/json"
               ]

if __name__ == "__main__":
    apiKey = "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"
    model = "gpt-4-1106-preview"

    if len(sys.argv) != 3:
        logger.error("Usage: python getter.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    outputdirectory = sys.argv[2]+"/"
    directories = walkIt.list_directories(directory)
    logger.info(directories)
    files = getter.consolidate_go_files(directory)
    logger.info(files)
    for url in webreources:
        htmlParser.fetchWebData(url,outputdirectory)


    aM = addGo.AssistantManager(apiKey, "goBot",outputdirectory)
    aM.updateAssistant()
    # aM.removeFilesFromAssistant()
    # aM.deleteAllFiles()
    # aM.uploadFilestoAssistant(files)
