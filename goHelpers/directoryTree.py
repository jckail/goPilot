# # Importing Libraries
# from directory_tree import display_tree

# # Main Method
# if __name__ == '__main__':
#     display_tree("/home/ec2-user/projects/databus/")



import os

def save_dir_tree_to_file(startpath, output_filepath, packages=None, exclude=None):
    if exclude is None:
        exclude = []
    if packages is None:
        packages = []

    project_name = os.path.basename(startpath.rstrip(os.sep))  # Get the project name from the directory path
    # Format the list of packages into a string
    packages_list_str = ', '.join(packages[:-1]) + ', and ' + packages[-1] if packages else ''

    startpath = startpath.rstrip(os.sep)  # Remove the trailing separator for consistency
    with open(output_filepath, 'w') as f:
        # Write the header with the list of packages
        f.write(f"This go project is called: {project_name}'s here is it's current directory tree.\n")
        if packages_list_str:
            f.write(f"{project_name}'s current Go Packages are: {packages_list_str}\n\n")

        # Write the root directory name first
        f.write('{}{}/\n'.format('', project_name))
        # Make sure the rest of the path is relative
        startpath_length = len(startpath)
        for root, dirs, files in os.walk(startpath, topdown=True):
            # Exclude hidden directories and specified directories/files
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in exclude]
            files = [fi for fi in files if not fi.startswith('.') and fi not in exclude]
            # Get the relative path after the startpath
            relative_root = root[startpath_length:].lstrip(os.sep)
            level = relative_root.count(os.sep)
            indent = '│   ' * level
            subindent = '│   ' * (level + 1)
            if relative_root and os.path.basename(root) not in exclude:
                f.write('{}├── {}/\n'.format(indent, os.path.basename(root)))
            for i, file in enumerate(files):
                end_char = '├── ' if i < len(files) - 1 else '└── '
                f.write('{}{}{}\n'.format(subindent, end_char, file))

def replace_suffix_in_file(input_filepath, output_filepath):
    with open(input_filepath, 'r') as f:
        content = f.read()

    # Replace the suffix
    new_content = content.replace('.go', '_go.txt')

    with open(output_filepath, 'w') as f:
        f.write(new_content)


# Example usage:
# exclusions = ['unwanted_directory', 'unwanted_file.go']
_packages = ['logging', 'serde', 'gcr', 'databus']

# Example usage:
save_dir_tree_to_file('/home/ec2-user/projects/databus/', 'additionalcontext/directory_tree.txt',packages=_packages)

# Example usage:
replace_suffix_in_file('additionalcontext/directory_tree.txt', 'additionalcontext/directory_tree_updated.txt')

def append_files_with_blurb(file1, file2, final_file, blurb):
    # Open the first file and read its contents
    with open(file1, 'r') as f:
        content1 = f.read()

    # Open the second file and read its contents
    with open(file2, 'r') as f:
        content2 = f.read()

    # Write the contents to the final file with the blurb in between
    with open(final_file, 'w') as f:
        f.write(content1 + '\n')
        f.write(blurb + '\n\n')
        f.write(content2)

# Example usage:
blurb_text = ("The directory tree above is a reflection of the actual directory tree, "
              "the directory tree below is similar to what i've given you without the directories, "
              "but simply take note that the contents of a \".go\" file are the same as the contents "
              "of a \"_go.txt\" file in that you can map these trees one to one and they are identical.")



append_files_with_blurb('additionalcontext/directory_tree.txt', 'additionalcontext/directory_tree_updated.txt', 'additionalcontext/projectDirectoryTree.txt', blurb_text)




