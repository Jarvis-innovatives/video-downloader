from django.contrib import admin
from .models import DownloadLog


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display = ('platform', 'format_type', 'quality', 'title', 'channel', 'created_at')
    list_filter = ('platform', 'format_type', 'created_at')
    search_fields = ('url', 'title', 'channel')
