import uuid

from django.db import models

# Create your models here.

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=100)
    username = None
    mfa_enabled = models.BooleanField(default=False)
    password_last_changed = models.DateTimeField(blank=True, null=True)
    failed_login_attempts = models.IntegerField(default=0)
    USERNAME_FIELD = 'email'

    REQUIRED_FIELDS = []

    token = None

