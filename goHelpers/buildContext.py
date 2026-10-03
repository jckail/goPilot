"""Build a reproducible, provider-free Go context executable for Linux."""

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile


MODULES = ("directoryTree.py", "exportContext.py", "getter.py")
BOOTSTRAP = b"from exportContext import main\nraise SystemExit(main())\n"
SHEBANG = b"#!/usr/bin/env -S python3 -I -B -S\n"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


class BuildError(OSError):
    def __init__(self, message, *, published=None, retained_stage=None):
        super().__init__(message)
        self.published = published
        self.retained_stage = retained_stage


def _resolve_parent(path):
    try:
        return path.resolve(strict=True)
    except RuntimeError as error:
        raise ValueError("cannot resolve output parent") from error


def archive_payload(helpers):
    """Prepare exact helper bytes and deterministic archive metadata in memory."""
    members = {name: (helpers / name).read_bytes() for name in MODULES}
    for name, data in members.items():
        ast.parse(data, filename=name)
    manifest = {
        "format": 1,
        "modules": {name: hashlib.sha256(data).hexdigest() for name, data in members.items()},
        "bootstrapSha256": hashlib.sha256(BOOTSTRAP).hexdigest(),
    }
    members["__main__.py"] = BOOTSTRAP
    members["manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
    payload = io.BytesIO()
    payload.write(SHEBANG)
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, members[name])
    return payload.getvalue()


def _publish(payload, destination):
    """Link a completely closed private sibling to a NEW destination only."""
    stage = None
    published = False
    failure = None
    cleanup_failure = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".gopilot-archive-",
                                         dir=destination.parent, delete=False) as handle:
            stage = Path(handle.name)
            if handle.write(payload) != len(payload):
                raise OSError("incomplete archive staging write")
            os.fchmod(handle.fileno(), 0o700)
        # Same-filesystem exclusive publication: never replace an existing entry.
        os.link(stage, destination)
        published = True
    except OSError as error:
        failure = error
    finally:
        if stage is not None:
            try:
                stage.unlink()
            except OSError as error:
                cleanup_failure = error
    if failure is not None or cleanup_failure is not None:
        message = str(failure if failure is not None else cleanup_failure)
        if failure is not None and cleanup_failure is not None:
            message += "; staging cleanup failed"
        raise BuildError(message, published=destination if published else None,
                         retained_stage=stage if cleanup_failure is not None and os.path.lexists(stage) else None)
    return destination


def build_context(output):
    if not str(output).strip():
        raise ValueError("output path must not be blank")
    helpers = Path(__file__).resolve().parent
    raw = Path(output)
    destination = _resolve_parent(raw.parent) / raw.name
    if not destination.parent.is_dir():
        raise ValueError("output parent must be an existing directory")
    if os.path.lexists(destination):
        raise ValueError("output already exists; choose a new file")
    if destination.is_relative_to(helpers.parent):
        raise ValueError("output must be outside the source checkout")
    return _publish(archive_payload(helpers), destination)


def main(argv=None):
    parser = Parser(description="Build a reproducible standalone Go context executable.")
    parser.add_argument("output", metavar="NEW_OUTPUT_FILE")
    try:
        args = parser.parse_args(argv)
        destination = build_context(args.output)
    except (OSError, ValueError, SyntaxError) as error:
        def bounded(value, limit):
            text = " ".join(str(value).split())
            if len(text) <= limit:
                return text
            half = (limit - 1) // 2
            return text[:half] + "…" + text[-(limit - half - 1):]

        parts = []
        if isinstance(error, BuildError):
            if error.published is not None:
                parts.append("complete artifact published: " + bounded(repr(str(error.published)), 180))
            if error.retained_stage is not None:
                parts.append("owned staging file retained: " + bounded(repr(str(error.retained_stage)), 180))
        # Reserve room for publication/cleanup state even when the cause is huge.
        parts.append(bounded(error, 260 if parts else 760))
        print("buildContext: " + "; ".join(parts), file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
