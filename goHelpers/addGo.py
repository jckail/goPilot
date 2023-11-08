import openai
import os
import shutil
import fnmatch
import time
#from dotenv import load_dotenv

# def get_openai_api_key():
#     try:
#         return os.getenv('OPENAI_API_KEY')
#     except KeyError:
#         raise KeyError("Environment variable 'OPENAI_API_KEY' not found.")


class AssistantManager:
    def __init__(self, assistantName,goHelperDirectory):
        # load_dotenv(dotenv_path=goHelperDirectory)
        # apiKey = get_openai_api_key()
        # print("helperDir",goHelperDirectory,"apiKey ",apiKey)
        self.client = openai.OpenAI()
        
        self.assistantName = assistantName
        self.my_assistant = self.fetchAssistant()
        self.execPath = goHelperDirectory
        print(self.execPath)
        self.uploadFiles = []
        self.promptPath = self.execPath+"prompt.txt"
        self.additionalContext = [] 
        
        self.updateAssistant()
        self.assistantFileNames = {}
        

    def removeFilesFromAssistant(self):
        print("\n Removing Files from Assistants: ")

        print("\n Processing files for: ", self.my_assistant.name)
        assistant_files = self.client.beta.assistants.files.list(
            assistant_id=self.my_assistant.id
        )
        for afile in assistant_files.data:
            print(
                "\n Removing: ",
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
        
    def getAdditionalContext(self):

        context_files = []
        addcontext = self.execPath + "additionalcontext/"
        for file in os.listdir(addcontext):
            if fnmatch.fnmatch(file, '*_context.txt'):
                context_files.append(os.path.join(addcontext, file))
        return context_files

    def uploadFilestoAssistant(self,uploadFiles,updateContext):
        if updateContext is True:
            self.additionalContext = self.getAdditionalContext()
            print("\n uploading additional context")
            uploadFiles += self.additionalContext
        self.uploadFiles = uploadFiles
        print("\n uploading ",str(len(self.uploadFiles))," files to assistant")
        
        print(
            "\n ",
            self.my_assistant.name,
            " has: "
            + str(len(list(self.my_assistant.file_ids)))
            + " files attached \n",
        )
        self.detectFileNames()
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
            self.copy_and_delete_file(uploadFile)
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
    
    def detectFileNames(self):
        self.my_assistant = self.client.beta.assistants.retrieve(self.my_assistant.id)
        if len(list(self.my_assistant.file_ids)) > 0:
            for fileId in self.my_assistant.file_ids:
                f = self.client.files.retrieve(fileId)
                self.assistantFileNames[f.filename] =  fileId
        print(self.my_assistant.name, " Assistant Files: ",self.assistantFileNames)

    def deleteDupe(self, uploadFile):
        basefile = os.path.basename(uploadFile)
        if  basefile in self.assistantFileNames.keys():
            print("duplicate detected: ", basefile)

            self.client.beta.assistants.files.delete(
                assistant_id=self.my_assistant.id, file_id=self.assistantFileNames[basefile]
            )
            ## this removes from OpenApi
            print("\n Deleting: ", basefile,self.assistantFileNames[basefile])
            self.client.files.delete(self.assistantFileNames[basefile])

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
    
    def updateAssistant(self):
        
        try:
            with open( self.promptPath, 'r') as file:
                prompt = file.read()
            print("\n Updating Assistant: ", self.assistantName)
            self.my_assistant = self.client.beta.assistants.update(
            self.my_assistant.id,
            instructions=prompt,
            #name="goBot",
            #tools=[{"type": "retrieval"}],
            #model="gpt-4-1106-preview",
            #file_ids=["file-abc123", "file-abc456"],
            )
            self.copy_and_delete_file(self.promptPath)
            print("\n Assistant Updated! : ", self.assistantName)
            return None
        except FileNotFoundError:
            print("The file prompt.txt was not found.")
            return "The file prompt.txt was not found."
        except Exception as e:
            print(f"An error occurred: {e}")
            return f"An error occurred: {e}"
        

    def copy_and_delete_file(self, source):
        uploads = self.execPath + "uploads/"
        print("\n",source,"\n")
        print("\n",uploads,"\n")
        try:
            # Copy the source file to the destination path
            shutil.copy(source, uploads)
            print(f"{source} copied to {uploads} successfully.")
            
            check = os.path.basename(source)
            # Check if the file exists at the destination path before deleting
            if os.path.isfile(uploads+check) and source not in self.additionalContext and source != self.promptPath:
                # Remove the source file
                os.remove(source)
                print(f"{source} has been deleted.")
            else:
                print(f"Did not remove source: {source}")
                
        except FileNotFoundError:
            print("The source file does not exist.")
        except PermissionError:
            print("Permission denied: unable to delete the source file.")
        except Exception as e:
            print(f"An error occurred: {e}")
        
    def createThread(self, addContent):

        if len(addContent) == 0: 
            print("No errors found")
            outcontent=f"""
            My code ran succesfully, that I stored in the "_go.txt" files I've uploaded.
            What are some items marked as "TODO"  or "//TODO" in any of the "_go.txt" files I've uploaded?
            """

        if len(addContent) == 1: 
            print("1 error found")
            outcontent=f"""I have encountered this error '{addContent[0]}' when running the 
            the code I gave you in the "_go.txt" files I've uploaded.
            Please provide me a solution or debugging steps so I can quickly resolve. 
            """

        if len(addContent) >= 1: 
            print(f"{str(len(addContent))} errors found")
            outcontent=f"""I have encountered these errors '{str(addContent)}' when running the 
            the code I gave you in the "_go.txt" files I've uploaded.
            Please provide me a solution or debugging steps so I can quickly resolve. 
            """

        thread = self.client.beta.threads.create()
        print("\n Thread Created: ", thread.id)
        url = "https://platform.openai.com/playground?assistant=asst_6Jqvv49JQCXZrTLMnSBb8xNM&mode=assistant&thread="
        print("View response here: ", url+str(thread.id))
        
        message = self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=outcontent)
        
        print("\n Message Created: ", message.id)
        
        run = self.client.beta.threads.runs.create(
            ## TODO can add in threads to the assistant client class
            thread_id=thread.id,
            assistant_id=self.my_assistant.id,
            instructions="It is important to remind you to review all of the documents I have uploaded"
            )
        print("\n Run Created: ", run.id)

        time.sleep(5)
        run = self.client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
            )
        timeoutSleep = 5 
        
        while run.status != "completed" and timeoutSleep < 125:
            timeoutSleep += 10
            print(f"Status: {str(run.status)} sleeping for 10 seconds total wait: {str(timeoutSleep)} seconds")
            time.sleep(10)
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
                )

        if run.status == "completed":
            print("\n Ai Response completed! \n ")
            print("\nView response here: ", url+str(thread.id),"\n","\n")
            messages = self.client.beta.threads.messages.list(
                thread_id=thread.id
                )
            return messages
        print("\n Failed! \n ")
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
