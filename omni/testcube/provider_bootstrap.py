"""Trusted stdin/exec bridge. The shared runner still owns all subprocesses."""
import json
import os
import sys


def main():
    with open(sys.argv[1], encoding="utf-8") as stream:
        spec = json.load(stream)
    fd = os.open(spec["stdin_path"], os.O_RDONLY | os.O_NOFOLLOW)
    os.dup2(fd, 0)
    os.close(fd)
    os.execv(spec["argv"][0], spec["argv"])


if __name__ == "__main__":
    main()
