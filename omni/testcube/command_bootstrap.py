"""Inside-isolation trusted exec handshake. No candidate module is imported."""
import os
import sys


def main() -> None:
    ready_fd = int(sys.argv[1])
    argv = sys.argv[2:]
    os.set_inheritable(ready_fd, False)
    os.write(ready_fd, b"ready\n")
    try:
        os.execv(argv[0], argv)
    except OSError:
        os.write(ready_fd, b"exec_failed\n")
        raise


if __name__ == "__main__":
    main()
