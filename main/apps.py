from django.apps import AppConfig


class MainConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "main"

    def ready(self):
        """Run startup tasks when Django initializes"""
        # Import here to avoid AppRegistryNotReady exception
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType
        from users.models import User
        from django.db.utils import OperationalError, ProgrammingError
        
        try:
            # Create Admin group if it doesn't exist
            admin_group, created = Group.objects.get_or_create(name='Admin')
            
            if created:
                print("[Startup] Created 'Admin' group")
            
            # Add all superusers to Admin group
            superusers = User.objects.filter(is_superuser=True)
            for superuser in superusers:
                if not superuser.groups.filter(name='Admin').exists():
                    superuser.groups.add(admin_group)
                    print(f"[Startup] Added superuser '{superuser.username}' to Admin group")
            
            # Ensure Advanced_user group exists for collections access
            advanced_group, created = Group.objects.get_or_create(name='Advanced_user')
            if created:
                print("[Startup] Created 'Advanced_user' group")
                
        except (OperationalError, ProgrammingError):
            # Database tables don't exist yet (during initial migrations)
            pass
