from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Meta:
        db_table = "User"

    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True, null=True)  # ✅ Fixed: Added unique constraint
    username = models.CharField(max_length=100, blank=True, null=True, unique=True)
    password = models.CharField(max_length=128, blank=True, null=True)  # ✅ Fixed: Increased length for hashing
    created_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name='created_users'
    )

    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith('pbkdf2_'):  # ✅ Hash password if not already hashed
            from django.contrib.auth.hashers import make_password
            self.password = make_password(self.password)
        super().save(*args, **kwargs)
