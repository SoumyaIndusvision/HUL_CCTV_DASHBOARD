from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from .serializers import UserSerializer  # Import serializer if needed for extra fields

User = get_user_model()

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Custom admin panel for managing users.
    """
    list_display = ('id', 'username', 'email', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'is_active', 'is_staff')}
        ),
    )

# Optional: Unregister the default User model if needed
# admin.site.unregister(User)
