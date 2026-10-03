"""Export Go analysis context locally with Python's standard library only."""

import argparse
import logging
import os
from pathlib import Path
import sys

import directoryTree
import getter


class ExportError(ValueError):
    def __init__(self, message, destination=None):
        super().__init__(message)
        self.destination = destination


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _resolve_existing(path):
    try:
        return path.resolve(strict=True)
    except RuntimeError as error:
        # CPython 3.10 reports symlink loops as RuntimeError rather than OSError.
        raise ValueError(str(error)) from error


def export_context(source, destination):
    """Create a new export; retain a clearly incomplete directory on failure.

    Existing destination entries and source-contained outputs are rejected.
    Reads are not an atomic snapshot of a concurrently changing source tree.
    """
    if not str(source).strip() or not str(destination).strip():
        raise ValueError("source and destination paths must not be blank")
    source = _resolve_existing(Path(source))
    if not source.is_dir():
        raise ValueError("source must be an existing directory")
    requested = Path(os.path.abspath(destination))
    # Resolve the parent only: following the final entry could follow a dangling
    # link and incorrectly treat its target as an available destination.
    parent = _resolve_existing(requested.parent)
    if not parent.is_dir():
        raise ValueError("destination parent must be an existing directory")
    destination = parent / requested.name
    if os.path.lexists(destination):
        raise ValueError("destination already exists; choose a new directory")
    if destination.is_relative_to(source):
        raise ValueError("destination must be outside the source directory")
    destination.mkdir(mode=0o700)
    try:
        package_map, outputs = getter.consolidate_go_files(
            str(source), output_directory=str(destination), strict_walk=True,
        )
        if not package_map:
            raise ValueError("no recognized non-test Go packages found")
        if len({os.path.normcase(getter.context_output_name(name))
                for name in package_map}) != len(package_map):
            raise ValueError("package output filenames collide on this platform")
        published = {Path(path).name for path in outputs}
        missing = [name for name in package_map
                   if getter.context_output_name(name) not in published]
        if missing:
            raise ValueError("package context publication failed: " + ", ".join(missing))
        package_map_path = destination / "package_map_context.txt"
        with package_map_path.open("x", encoding="utf-8") as handle:
            handle.write(getter.format_package_map(package_map, outputs))
        tree = destination / "directory_tree.txt"
        legacy = destination / "directory_tree_updated.txt"
        directoryTree.save_dir_tree_to_file(
            str(source), str(tree), packages=sorted(package_map), strict_walk=True,
        )
        directoryTree.replace_suffix_in_file(str(tree), str(legacy), generated_tree=True)
        directoryTree.append_files_with_blurb(
            str(tree), str(legacy), str(destination / "projectDirectoryTree_context.txt"),
            "The first tree shows the discovered source hierarchy with escaped labels "
            "and non-followed directory symlink leaves. The second is a legacy "
            "suffix display view, not individual generated outputs. Use "
            "package_map_context.txt and root-relative package source markers "
            "as the authoritative mapping. Aggregated context is not compilable Go.",
        )
    except (OSError, ValueError) as error:
        raise ExportError(str(error), destination) from error
    return destination


def main(argv=None):
    parser = Parser(description="Export complete local Go analysis context without a provider.")
    parser.add_argument("source", metavar="SOURCE")
    parser.add_argument("destination", metavar="NEW_OUTPUT_DIR")
    try:
        args = parser.parse_args(argv)
        previous_logging_threshold = logging.root.manager.disable
        # This standalone command emits one completion path or one diagnostic.
        # Restore the caller's logging state even when export fails.
        logging.disable(logging.CRITICAL)
        try:
            destination = export_context(args.source, args.destination)
        finally:
            logging.disable(previous_logging_threshold)
    except (OSError, ValueError) as error:
        retained = error.destination if isinstance(error, ExportError) else None
        location = ("; incomplete output retained at " + repr(str(retained))[:400]
                    if retained is not None else "")
        detail = " ".join(str(error).split())[:350]
        print(f"Context export failed{location}: {detail}"[:799], file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
