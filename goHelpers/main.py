import logging
import walkIt
import addGo
import getter
#import getterTwo
import sys
import htmlParser
import directoryTree

# Configure logging to write to stdout, which can be seen in the shell
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()

webreources = [
    "https://go.dev/doc/effective_go",
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

    if len(sys.argv) != 5:
        logger.error("Usage: python getter.py <directory>")
        sys.exit(1)

    updateContext = False
    deleteAll = False

    directory = str(sys.argv[1])
    goHelperDirectory = str(sys.argv[2])+"/"
    uc = str(sys.argv[3])
    if uc == "true":
        updateContext = True

    da = str(sys.argv[4])
    if da == "true":
        deleteAll = True

    logger.info("%s %s %s %s", directory, goHelperDirectory, uc, da)

    directories = walkIt.list_directories(directory)
    logger.info(directories)
    #The OG approach
    package_map, files = getter.consolidate_go_files(directory)
    # maximum of 20 
    #files = getterTwo.get_and_save_go_files(directory)
    print("wtf", files)

    package_map_context = goHelperDirectory+"results/package_map_context.txt"
    # Write to the .txt file
    with open(package_map_context, 'w') as file:
        for package_name, fs in package_map.items():
            file.write(f"'{package_name}._go.txt' contains {fs}\n")
    files.append(package_map_context)
    print("wtf", files)
    _packages = ['logging', 'serde', 'gcr', 'databus']

    # Example usage:
    directoryTree.save_dir_tree_to_file(directory, goHelperDirectory+'results/directory_tree.txt',packages=_packages)

    # Example usage:
    directoryTree.replace_suffix_in_file(goHelperDirectory+'results/directory_tree.txt', goHelperDirectory+'results/directory_tree_updated.txt')


    # Example usage:
    blurb_text = ("The directory tree above is a reflection of the actual directory tree, "
                "the directory tree below is similar to what i've given you without the directories, "
                "but simply take note that the contents of a \".go\" file are the same as the contents "
                "of a \"_go.txt\" file in that you can map these trees one to one and they are identical.")



    files.append(directoryTree.append_files_with_blurb(goHelperDirectory+'results/directory_tree.txt', goHelperDirectory+'results/directory_tree_updated.txt', goHelperDirectory+'results/projectDirectoryTree_context.txt', blurb_text))

    print(files)
    if updateContext is True:
        print('Updating Context')
        logger.info(files)
        for url in webreources:
            htmlParser.fetchWebData(url,goHelperDirectory)


    aM = addGo.AssistantManager( "goBot", goHelperDirectory)
    if deleteAll is True:
        aM.removeFilesFromAssistant()
        aM.deleteAllFiles()
    aM.uploadFilestoAssistant(files,updateContext)


# lastly if there is an error pass that as a new thread to the assistant 