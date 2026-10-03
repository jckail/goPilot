# # Importing Libraries
# from directory_tree import display_tree

# # Main Method
# if __name__ == '__main__':
#     display_tree("/home/ec2-user/projects/")



import os

def save_dir_tree_to_file(startpath, output_filepath, packages=None, exclude=None, *, strict_walk=False):
    if exclude is None:
        exclude = []
    if packages is None:
        packages = []

    project_name = os.path.basename(startpath.rstrip(os.sep))  # Get the project name from the directory path
    # Format the list of packages into a string
    packages_list_str = (packages[0] if len(packages) == 1 else
                         ', '.join(packages[:-1]) + ', and ' + packages[-1]) if packages else ''

    startpath = startpath.rstrip(os.sep)  # Remove the trailing separator for consistency
    with open(output_filepath, 'w', encoding='utf-8') as f:
        # Write the header with the list of packages
        f.write(f"This go project is called: {project_name}'s here is it's current directory tree.\n")
        if packages_list_str:
            f.write(f"{project_name}'s current Go Packages are: {packages_list_str}\n\n")

        # Write the root directory name first
        f.write('{}{}/\n'.format('', project_name))
        # Make sure the rest of the path is relative
        startpath_length = len(startpath)
        def raise_walk_error(error):
            raise error

        walk_options = {"onerror": raise_walk_error} if strict_walk else {}
        for root, dirs, files in os.walk(startpath, topdown=True, **walk_options):
            # Exclude hidden directories and specified directories/files
            # Mutate dirs so os.walk also visits descendants in stable order.
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in exclude)
            files = sorted(fi for fi in files if not fi.startswith('.') and fi not in exclude)
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
    """Convert terminal Go file suffixes in generated tree entries only.

    Other text, directory names and line endings remain byte-for-byte intact.
    This legacy view does not replace the authoritative package map.
    """
    import re

    with open(input_filepath, 'rb') as f:
        content = f.read()

    # Generated file lines start with tree indentation and a branch marker.
    # A directory ends in '/', so it cannot match a terminal '.go' suffix.
    file_entry = r'(?m)^((?:│   )+(?:├── |└── )[^\r\n]*)\.go(?=\r?$)'.encode('utf-8')
    new_content = re.sub(file_entry, rb'\1_go.txt', content)

    with open(output_filepath, 'wb') as f:
        f.write(new_content)

def append_files_with_blurb(file1, file2, final_file, blurb):
    # Open the first file and read its contents
    with open(file1, 'r', encoding='utf-8') as f:
        content1 = f.read()

    # Open the second file and read its contents
    with open(file2, 'r', encoding='utf-8') as f:
        content2 = f.read()

    # Write the contents to the final file with the blurb in between
    with open(final_file, 'w', encoding='utf-8') as f:
        f.write(content1 + '\n')
        f.write(blurb + '\n\n')
        f.write(content2)
    return os.path.abspath(final_file)


if __name__ == "__main__":
    project_path = '/home/ec2-user/projects/'
    # Example usage:
    # exclusions = ['unwanted_directory', 'unwanted_file.go']
    _packages = ['logging', 'serde']

    # Example usage:
    save_dir_tree_to_file('/home/ec2-user/projects/', 'results/directory_tree.txt',packages=_packages)

    # Example usage:
    replace_suffix_in_file('results/directory_tree.txt', 'results/directory_tree_updated.txt')


    # Example usage:
    blurb_text = ("The directory tree above is a reflection of the actual directory tree, "
                "the directory tree below is similar to what i've given you without the directories, "
                "but simply take note that the contents of a \".go\" file are the same as the contents "
                "of a \"_go.txt\" file in that you can map these trees one to one and they are identical.")



    append_files_with_blurb('results/directory_tree.txt', 'results/directory_tree_updated.txt', 'results/projectDirectoryTree.txt', blurb_text)


