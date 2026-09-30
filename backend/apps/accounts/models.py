from django.contrib.auth.models import AbstractUser
from django.db import models

from llm import chat_modes


class User(AbstractUser):
    """Local user. No LDAP/SSO/OAuth - local credentials only.

    chat_mode: per-user communication mode (work | introvert | super_introvert),
    persisted locally, never synced anywhere. Default: work.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        ANALYST = "analyst", "Analyst"
        VIEWER = "viewer", "Viewer"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.ANALYST)
    chat_mode = models.CharField(max_length=24, default=chat_modes.DEFAULT_MODE)

    def save(self, *args, **kwargs):
        self.chat_mode = chat_modes.normalize_mode(self.chat_mode)
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def can_edit(self) -> bool:
        return self.role in {self.Role.ADMIN, self.Role.ANALYST}
