"""Own and remove only the snapshot created by this workflow attempt."""

import json
import os
import stat
import sys
import tempfile
from pathlib import Path


def identity(path):
    info = path.lstat()
    return [info.st_dev, info.st_ino]


def materialize(value, parent):
    if not value:
        raise ValueError("A complete authoritative environment is required")
    directory = Path(tempfile.mkdtemp(prefix="logs-ai-compose-", dir=parent))
    path = directory / "compose.env"
    record = {"directory": str(directory), "directoryIdentity": identity(directory)}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except BaseException:
        # Never unlink a path that O_EXCL refused to create.
        try:
            directory.rmdir()
        except OSError:
            pass
        raise
    record.update(path=str(path), fileIdentity=identity(path))
    try:
        with os.fdopen(fd, "w") as file:
            file.write(value)
    except BaseException:
        cleanup(record)
        raise
    return record


def cleanup(record):
    directory, path = Path(record["directory"]), Path(record["path"])
    if path != directory / "compose.env" or identity(directory) != record["directoryIdentity"]:
        raise ValueError("Snapshot directory ownership changed; refusing cleanup")
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if (
            identity(path) != record["fileIdentity"]
            or not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
        ):
            raise ValueError("Snapshot file was replaced; refusing cleanup")
        path.unlink()
    directory.rmdir()  # Never recursively delete unexpected contents.


def main():
    if sys.argv[1:] == ["create"]:
        record = materialize(os.environ.get("DOKPLOY_ENV_SNAPSHOT"), os.environ["RUNNER_TEMP"])
        try:
            if any(c in record["path"] for c in "\r\n"):
                raise ValueError("Invalid snapshot path")
            with open(os.environ["GITHUB_ENV"], "a") as file:
                file.write("DOKPLOY_ENV_FILE=" + record["path"] + "\n")
                file.write("DOKPLOY_SNAPSHOT_OWNERSHIP=" + json.dumps(record) + "\n")
        except BaseException:
            cleanup(record)
            raise
    elif sys.argv[1:] == ["cleanup"]:
        value = os.environ.get("DOKPLOY_SNAPSHOT_OWNERSHIP")
        if value:
            cleanup(json.loads(value))
        # No ownership export means creation did not finish. Do not use a fallback path.
    else:
        raise SystemExit("Use create or cleanup")


if __name__ == "__main__":
    main()
