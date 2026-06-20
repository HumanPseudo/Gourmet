from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates or updates a superuser from environment variables"

    def handle(self, *args, **options):
        User = get_user_model()
        email = os.environ.get("SUPERUSER_EMAIL", "admin@example.com")
        password = os.environ.get("SUPERUSER_PASSWORD", "admin")
        name = os.environ.get("SUPERUSER_NAME", "Admin")

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.name = name
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superuser updated: {email}"))
        else:
            User.objects.create_superuser(
                email=email,
                password=password,
                name=name,
            )
            self.stdout.write(self.style.SUCCESS(f"Superuser created: {email}"))
