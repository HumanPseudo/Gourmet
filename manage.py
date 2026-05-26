#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import sys


def main() -> None:
    """Run administrative tasks."""
    import os  # noqa: PLC0415
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gourmet.settings")
    from django.core.management import execute_from_command_line  # noqa: PLC0415

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
