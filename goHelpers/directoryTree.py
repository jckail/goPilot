# # Importing Libraries
# from directory_tree import display_tree

# # Main Method
# if __name__ == '__main__':
#     display_tree("/home/ec2-user/projects/")



import os

def _display_label(value):
    """Escape ambiguous display characters without changing filesystem names."""
    parts = []
    for character in value:
        code = ord(character)
        if character == "\\":
            parts.append("\\\\")
        elif character.isprintable():
            parts.append(character)
        elif code <= 0xff:
            parts.append(f"\\x{code:02x}")
        elif code <= 0xffff:
            parts.append(f"\\u{code:04x}")
        else:
            parts.append(f"\\U{code:08x}")
    return ''.join(parts)


def save_dir_tree_to_file(startpath, output_filepath, packages=None, exclude=None, *, strict_walk=False):
    """Render a sorted source hierarchy; directory symlinks are non-followed leaves.

    Discovery finishes before output opens. This is not a filesystem snapshot.
    """
    exclude = [] if exclude is None else exclude
    packages = [] if packages is None else packages
    startpath = os.path.abspath(os.path.normpath(startpath))
    project_name = _display_label(os.path.basename(startpath) or startpath)
    displayed_packages = [_display_label(name) for name in packages]
    packages_list_str = (displayed_packages[0] if len(displayed_packages) == 1 else
                         ', '.join(displayed_packages[:-1]) + ', and ' + displayed_packages[-1]) if displayed_packages else ''

    def raise_walk_error(error):
        raise error

    inventory = {}
    walk_options = {"onerror": raise_walk_error} if strict_walk else {}
    for root, dirs, files in os.walk(startpath, topdown=True, **walk_options):
        # os.walk's default followlinks=False preserves the existing discovery API.
        dirs[:] = sorted(name for name in dirs if not name.startswith('.') and name not in exclude)
        files = sorted(name for name in files if not name.startswith('.') and name not in exclude)
        inventory[os.path.relpath(root, startpath)] = [
            (name, True, os.path.islink(os.path.join(root, name))) for name in dirs
        ] + [(name, False, False) for name in files]

    with open(output_filepath, 'w', encoding='utf-8') as handle:
        handle.write(f"This go project is called: {project_name}'s here is it's current directory tree.\n")
        if packages_list_str:
            handle.write(f"{project_name}'s current Go Packages are: {packages_list_str}\n\n")
        handle.write(project_name + ('' if project_name.endswith(os.sep) else '/') + '\n')
        # Stack avoids Python recursion limits and carries each ancestor's branch state.
        stack = []

        def push_children(key, prefix):
            entries = inventory.get(key, [])
            for index in range(len(entries) - 1, -1, -1):
                name, is_directory, is_link = entries[index]
                stack.append((key, name, is_directory, is_link, prefix, index == len(entries) - 1))

        push_children('.', '')
        while stack:
            key, name, is_directory, is_link, prefix, last = stack.pop()
            label = _display_label(name) + ('/' if is_directory else '')
            if is_link:
                label += ' [directory symlink; not followed]'
            handle.write(prefix + ('└── ' if last else '├── ') + label + '\n')
            if is_directory and not is_link:
                child_key = name if key == '.' else os.path.join(key, name)
                push_children(child_key, prefix + ('    ' if last else '│   '))

def replace_suffix_in_file(input_filepath, output_filepath, *, generated_tree=False):
    """Convert terminal Go file suffixes in generated tree entries only.

    Other text, directory names and line endings remain byte-for-byte intact.
    This legacy view does not replace the authoritative package map.
    """
    import re

    with open(input_filepath, 'rb') as f:
        content = f.read()

    # Generated file lines start with tree indentation and a branch marker.
    # A directory ends in '/', so it cannot match a terminal '.go' suffix.
    indentation = r'(?:│   |    )*' if generated_tree else r'(?:│   )+'
    file_entry = (r'(?m)^(' + indentation + r'(?:├── |└── )[^\r\n]*)\.go(?=\r?$)').encode('utf-8')
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
    replace_suffix_in_file('results/directory_tree.txt', 'results/directory_tree_updated.txt', generated_tree=True)


    # Example usage:
    blurb_text = ("The first tree shows the discovered source hierarchy; "
                  "the second is a suffix display view, not individual generated outputs. "
                  "Use the package map for actual per-package context source identities.")



    append_files_with_blurb('results/directory_tree.txt', 'results/directory_tree_updated.txt', 'results/projectDirectoryTree.txt', blurb_text)


