import openai
import os


class AssistantManager:
    def __init__(self, apiKey, uploadFiles, assistantName):
        self.client = openai.OpenAI(api_key=apiKey)
        self.uploadFiles = uploadFiles
        self.assistantName = assistantName
        self.my_assistant = self.fetchAssistant()

    def removeFilesFromAssistant(self):
        print("\n Removing Files from Assistants: ")

        print("\n Processing files for: ", self.my_assistant.name)
        assistant_files = self.client.beta.assistants.files.list(
            assistant_id=self.my_assistant.id
        )
        for afile in assistant_files.data:
            print(
                "\n Removing: ",
                self.client.files.retrieve(afile.id).name,
                print(""),
                str(afile.id),
                " from ",
                self.my_assistant.name,
            )
            if afile.id not in self.client.files.list():
                deleted_assistant_file = self.client.beta.assistants.files.delete(
                    assistant_id=self.my_assistant.id, file_id=afile.id
                )
        self.my_assistant = self.client.beta.assistants.retrieve(self.my_assistant.id)

        print(
            "\n",
            self.my_assistant.name,
            " has: ",
            str(len(list(self.my_assistant.file_ids))),
            " files attached \n",
        )
        print("\n removeFileFromAssistant Completed! \n")

    def deleteAllFiles(self):
        print("deleting all files")

        print("\nBegining Deleting: ", len(list(self.client.files.list())), " files")

        if len(list(self.client.files.list())) > 0:
            for file in self.client.files.list():
                f = self.client.files.retrieve(file.id)
                print("\n Deleting: ", f.filename, f.purpose, f.id)
                self.client.files.delete(f.id)

        if len(list(self.client.files.list())) == 0:
            print("All files deleted", self.client.files.list())
            return True
        else:
            return False

    def uploadFilestoAssistant(self):
        print("\n uploading ",str(len(self.uploadFiles))," files to assistant")

        print(
            "\n ",
            self.my_assistant.name,
            " has: "
            + str(len(list(self.my_assistant.file_ids)))
            + " files attached \n",
        )

        for uploadFile in self.uploadFiles:
            self.deleteDupe(uploadFile)

            print("\n Uploading: ", uploadFile)

            filex = self.client.files.create(
                file=open(uploadFile, "rb"), purpose="assistants"
            )
            assistant_file = self.client.beta.assistants.files.create(
                assistant_id=self.my_assistant.id, file_id=filex.id
            )
            print(
                self.client.files.retrieve(assistant_file.id).filename,
                " ",
                str(assistant_file.id),
                " added to ",
                self.my_assistant.name,
            )
        self.my_assistant = self.client.beta.assistants.retrieve(self.my_assistant.id)
        print(
            "\n ",
            self.my_assistant.name,
            " has: ",
            str(len(list(self.my_assistant.file_ids))),
            " files attached \n",
        )

        if len(list(self.my_assistant.file_ids)) >= len(self.uploadFiles):
            print("\n uploadFilestoAssistant Completed! \n")
            return True
        return False

    def deleteDupe(self, uploadFile):
        for fileId in self.my_assistant.file_ids:
            f = self.client.files.retrieve(fileId)
            if f.filename == os.path.basename(uploadFile):
                print("duplicate detected: ", f.filename)

                self.client.beta.assistants.files.delete(
                    assistant_id=self.my_assistant.id, file_id=f.id
                )
                print(
                    "duplicate deleted: ", f.filename, " from: ", self.my_assistant.name
                )
        self.my_assistant = self.client.beta.assistants.retrieve(self.my_assistant.id)

    def fetchAssistant(self):
        print("\n Fetching Assistant: ", self.assistantName)
        my_assistants = self.client.beta.assistants.list(
            order="desc",
        )
        for ai in my_assistants.data:
            if ai.name == self.assistantName:
                print("\n Found: ", ai.name)
                return self.client.beta.assistants.retrieve(ai.id)
        return None


# Example of how to use the class
if __name__ == "__main__":
    apiKey = "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"
    model = "gpt-4-1106-preview"
    file_path = "/Users/jkail/projects/databus/gcr/"
    file_name = "gcr.txt"
    uploadFile = file_path + file_name

    assistantManager = AssistantManager(apiKey, [uploadFile], "goBot")

    # Use the methods of the AssistantManager class
    # assistantManager.deleteAllFiles()
    # assistantManager.removeFilesFromAssistants()
    assistantManager.uploadFilestoAssistant()
