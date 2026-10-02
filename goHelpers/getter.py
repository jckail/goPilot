import os
import re
import logging
import ast
import json
from collections import defaultdict

# Configure logging to write to stdout, which can be seen in the shell
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()


# Keep comments and string literals opaque when identifying header declarations.
_GO_TOKENS = re.compile(
    r'(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)'
    r'|(?P<string>"(?:\\.|[^"\\])*"|`[^`]*`)'
    r"|(?P<identifier>[^\W\d]\w*)|(?P<other>\S)"
)


def _extract_go_header(contents):
    """Return package, complete import specs, and source without its header.

    This is a bounded header reader, not a Go compiler. Only imports following
    the package clause are collected; comments and source-body strings survive.
    """
    tokens = [m for m in _GO_TOKENS.finditer(contents) if m.lastgroup != "comment"]
    if (len(tokens) < 2 or tokens[0].group() != "package"
            or tokens[1].lastgroup != "identifier"):
        return None, set(), contents

    package = tokens[1].group()
    spans = [(tokens[0].start(), tokens[1].end())]
    imports = set()
    index = 2

    def read_spec(position):
        alias = ""
        if position < len(tokens) and (
                tokens[position].lastgroup == "identifier"
                or tokens[position].group() == "."):
            alias = tokens[position].group() + " "
            position += 1
        if position >= len(tokens) or tokens[position].lastgroup != "string":
            return None, position
        literal = tokens[position].group()
        try:
            # Go's valid import-path escapes share Python's string escape forms.
            # Raw Go literals discard carriage returns and have no escapes.
            path = (literal[1:-1].replace("\r", "") if literal.startswith("`")
                    else ast.literal_eval(literal))
            literal = json.dumps(path, ensure_ascii=False)
        except (ValueError, SyntaxError):
            # Invalid source is analysis input too; do not invent a new path.
            pass
        return alias + literal, position + 1

    while index < len(tokens):
        if tokens[index].group() == ";":
            index += 1
            continue
        if tokens[index].group() != "import":
            break
        start = tokens[index].start()
        index += 1
        collected = set()
        if index < len(tokens) and tokens[index].group() == "(":
            index += 1
            while index < len(tokens) and tokens[index].group() != ")":
                if tokens[index].group() == ";":
                    index += 1
                    continue
                spec, index = read_spec(index)
                if spec is None:
                    return package, imports, _remove_spans(contents, spans)
                collected.add(spec)
            if index >= len(tokens):
                break
            index += 1
        else:
            spec, index = read_spec(index)
            if spec is None:
                break
            collected.add(spec)
        imports.update(collected)
        end = tokens[index - 1].end()
        if index < len(tokens) and tokens[index].group() == ";":
            end = tokens[index].end()
            index += 1
        spans.append((start, end))
    return package, imports, _remove_spans(contents, spans)


def _remove_spans(contents, spans):
    for start, end in reversed(spans):
        contents = contents[:start] + contents[end:]
    return contents


def consolidate_go_files(directory):
    """Write per-package analysis context, not a guaranteed compilable Go file.

    Equivalent literal paths with the same alias are deduplicated and emitted
    as quoted paths. Different aliases, duplicate
    declarations, build tags and cgo context can still prevent compilation.
    """
    outputs = []

    # Dictionary to hold the package contents
    package_contents = {}

    # Dictionary to hold the unique imports for each package
    package_imports = {}

    package_map = defaultdict(list)

    # Traverse through the directory
    for subdir, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".go") and not file.endswith("_test.go"):
                logger.info(f"Processing file: {file}")
                file_path = os.path.join(subdir, file)

                with open(file_path, "r") as f:
                    contents = f.read()
                    contents = contents + f"\n // This is the end of {file}\n"

                    package_name, imports, contents = _extract_go_header(contents)
                    if package_name:

                        # Initialize package contents and imports if not present
                        if package_name not in package_contents:
                            package_contents[package_name] = ""
                            package_imports[package_name] = set()

                        package_imports[package_name].update(imports)
                        #contents = f"// This is the start of {file}" + contents
                        #print(contents)
                        # Append the contents to the package contents
                        package_contents[package_name] += f"\n // This is the start of {file} "
                        package_contents[package_name] += contents + "\n"
                        #print(package_contents[package_name])
                        package_map[package_name].append(file)
    # Now create the consolidated .txt files with imports and package declarations
    for package_name, contents in package_contents.items():
        # Prepend unique imports and the package name to the content
        unique_imports = "\n".join(sorted(package_imports[package_name]))
        import_block = f"import (\n{unique_imports}\n)\n\n" if unique_imports else ""
        final_content = f"package {package_name}\n\n{import_block}{contents}"

        # Write the final content to the file in the passed directory
        output_file_path = os.path.join(directory, f"{package_name}_go.txt")
        try:
            with open(output_file_path, "w") as f:
                f.write(final_content)
                logger.info(f"File written: {output_file_path}")
                outputs.append(output_file_path)
        except IOError as e:
            logger.error(f"Failed to write file: {output_file_path}, due to {e}")

    logger.info("Consolidation complete.")
    return package_map, outputs


# The directory to consolidate should be passed as a command-line argument
if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        logger.error("Usage: python getter.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    consolidate_result = consolidate_go_files(directory)
    logger.info(consolidate_result)
