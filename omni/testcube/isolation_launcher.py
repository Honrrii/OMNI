"""Standalone trusted exec wrapper; never imported from candidate code.

Open Bubblewrap's out-of-band status descriptor before exec, without expanding
the shared process runner's descriptor API. Bubblewrap closes this descriptor
in its sandbox child; only the outside monitor writes to it.
"""
import json
import os
import sys


def main() -> None:
    spec_path, status_path = sys.argv[1:]
    with open(spec_path, encoding="utf-8") as stream:
        spec = json.load(stream)
    status_fd = os.open(status_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.set_inheritable(status_fd, True)
    ready_fd = os.open(status_path + ".ready", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    os.set_inheritable(ready_fd, True)
    argv = spec["isolation_argv"]
    argv = [argv[0], "--json-status-fd", str(status_fd), *argv[1:], "--",
            "/runtime/bin/python", "-I", "/bootstrap.py", str(ready_fd), *spec["target_argv"]]
    os.execv(argv[0], argv)


if __name__ == "__main__":
    main()
