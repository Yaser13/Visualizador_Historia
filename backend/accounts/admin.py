from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'country', 'organization', 'language', 'created_at')
    list_filter = ('language',)
    list_select_related = ('user',)
    search_fields = ('display_name', 'user__username', 'user__email', 'organization')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
