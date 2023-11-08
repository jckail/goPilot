import os

def get_and_save_go_files(directory):
    go_file_paths = []

    # Traverse through the directory
    for subdir, dirs, files in os.walk(directory):
        for file in files:
            # Check if the file has .go extension and not already a _go.txt file
            if file.endswith(".go") and not file.endswith("_go.txt"):
                # Construct the full file path
                file_path = os.path.join(subdir, file)
                # Construct the new file path with _go.txt suffix
                new_file_path = file_path[:-3] + "_go.txt"
                print(file_path)
                print(new_file_path)
                # Open the .go file and read contents
                with open(file_path, 'r') as go_file:
                    contents = go_file.read()

                # Save contents to a new _go.txt file
                with open(new_file_path, 'w') as new_file:
                    new_file.write(contents)

                # Append the path of the new file to the list
                go_file_paths.append(new_file_path)
    
    # Return the list of paths
    print(go_file_paths)
    return go_file_paths

# The directory to consolidate should be passed as a command-line argument
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        sys.exit(1)

    directory = sys.argv[1]
    go_file_paths = get_and_save_go_files(directory)

