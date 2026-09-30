from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create a local admin user (run once after install). Example: create_admin -u admin -p 'some-pass'"

    def add_arguments(self, parser):
        parser.add_argument("-u", "--username", required=True)
        parser.add_argument("-p", "--password", required=True)

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"role": User.Role.ADMIN, "is_staff": True, "is_superuser": True},
        )
        if not created:
            user.set_password(password)
            user.role = User.Role.ADMIN
            user.is_superuser = True
            user.is_staff = True
            user.save()
            self.stdout.write(self.style.WARNING(f"Updated existing user '{username}' with a new password."))
        else:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created admin user '{username}'."))
