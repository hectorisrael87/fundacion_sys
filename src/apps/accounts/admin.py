from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "cargo", "telefono", "area", "activo")
    search_fields = ("user__username", "user__first_name", "user__last_name", "cargo", "telefono", "area", "ci")
    list_filter = ("activo", "area")
