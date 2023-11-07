import openai
import os


def removeFilesFromAssistants(client):
    print("\n Removing Files from Assistants: ")
    my_assistants = client.beta.assistants.list(
        order="desc",
    )
    for ai in my_assistants.data:
        print("\n Processing files for: ", ai.name)
        assistant_files = client.beta.assistants.files.list(assistant_id=ai.id)
        for afile in assistant_files.data:
            print(
                "\n Removing: ",
                client.files.retrieve(afile.id).name,
                print(""),
                str(afile.id),
                " from ",
                ai.name,
            )
            if afile.id not in client.files.list():
                deleted_assistant_file = client.beta.assistants.files.delete(
                    assistant_id=ai.id, file_id=afile.id
                )
        assistant_files = client.beta.assistants.files.list(assistant_id=ai.id)

        print(
            "\n",
            ai.name,
            " has: ",
            str(len(list(assistant_files))),
            " files attached \n",
        )
    print("\n removeFileFromAssistant Completed! \n")


def deleteAllFiles(client):
    print("deleting all files")

    print("\nBegining Deleting: ", len(list(client.files.list())), " files")

    if len(list(client.files.list())) > 0:
        for file in client.files.list():
            f = client.files.retrieve(file.id)
            print("\n Deleting: ", f.filename, f.purpose, f.id)
            client.files.delete(f.id)

    if len(list(client.files.list())) == 0:
        print("All files deleted", client.files.list())
        return True
    else:
        return False


def uploadFilestoAssistant(client, assistantId, uploadFiles):
    print("\n uploading files to assistant")
    my_assistant = client.beta.assistants.retrieve(assistantId)

    print(
        "\n ",
        my_assistant.name,
        " has: " + str(len(list(my_assistant.file_ids))) + " files attached \n",
    )

    for uploadFile in uploadFiles:
        deleteDupe(client, my_assistant, uploadFile)

        print("\n Uploading: ", uploadFile)

        filex = client.files.create(file=open(uploadFile, "rb"), purpose="assistants")
        assistant_file = client.beta.assistants.files.create(
            assistant_id=my_assistant.id, file_id=filex.id
        )
        print(
            client.files.retrieve(assistant_file.id).filename,
            " ",
            str(assistant_file.id),
            " added to ",
            my_assistant.name,
        )

    assistant_files = client.beta.assistants.files.list(assistant_id=my_assistant.id)
    print(
        "\n ",
        my_assistant.name,
        " has: ",
        str(len(list(assistant_files))),
        " files attached \n",
    )

    if len(list(assistant_files)) >= len(uploadFiles):
        print("\n uploadFilestoAssistant Completed! \n")
        return True
    return False


def deleteDupe(client, my_assistant, uploadFile):
    for fileId in my_assistant.file_ids:
        f = client.files.retrieve(fileId)
        if f.filename == os.path.basename(uploadFile):
            print("duplicate detected: ", f.filename)

            client.beta.assistants.files.delete(
                assistant_id=my_assistant.id, file_id=f.id
            )
            print("duplicate deleted: ", f.filename, " from: ", my_assistant.name)


def fetchAssistant(client, name):
    print("\n Fetching Assistant: ", name)
    my_assistants = client.beta.assistants.list(
        order="desc",
    )
    for ai in my_assistants.data:
        if ai.name == name:
            print("\n Found: ", ai.name)
            return ai.id
    return None


if __name__ == "__main__":
    # assistantId = "asst_6Jqvv49JQCXZrTLMnSBb8xNM"
    apiKey = "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"
    model = "gpt-4-1106-preview"
    file_path = "/Users/jkail/projects/databus/gcr/"
    file_name = "gcr.txt"
    uploadFile = file_path + file_name

    client = openai.OpenAI(api_key=apiKey)

    # deleteAllFiles(client)
    # removeFilesFromAssistants(client)
    aiId = fetchAssistant(client, "goBot")
    uploadFilestoAssistant(client, aiId, [uploadFile])
