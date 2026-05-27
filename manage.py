#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
from django.core.management import execute_from_command_line
import sys
import os

def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gourmet.settings")
    execute_from_command_line(sys.argv)

if __name__ == "__main__":
    main()
