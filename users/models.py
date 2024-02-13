from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    username = models.CharField(max_length=150, primary_key=True)
    email = models.EmailField(unique= False, blank=True, null=True)
    phone = models.CharField(max_length=16, blank=True, null=True)

    def __str__(self):
        return self.username

    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    def is_admin(self):
        if self.groups.filter(name='Admin').exists():
            return True
        return False
    
    def is_advanced_user(self):
        if self.groups.filter(name='Advanced_user').exists():
            return True
        return False