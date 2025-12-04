from django.contrib import admin
from .models import User, VerificationDoc

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'role', 'is_verified')
    list_editable = ('is_verified',) # Allows quick verification

admin.site.register(VerificationDoc)