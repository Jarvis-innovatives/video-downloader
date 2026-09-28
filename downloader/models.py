from django.db import models


class DownloadLog(models.Model):
    PLATFORM_CHOICES = [
        ('YouTube', 'YouTube'),
        ('Instagram', 'Instagram'),
        ('TikTok', 'TikTok'),
        ('MovieBox', 'MovieBox'),
    ]

    FORMAT_CHOICES = [
        ('video', 'Video'),
        ('mp3', 'MP3'),
    ]

    url = models.URLField(max_length=500)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    format_type = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='video')
    quality = models.CharField(max_length=20, default='1080p')
    title = models.CharField(max_length=255, blank=True, default='')
    channel = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.platform} - {self.format_type} ({self.quality}): {self.title or self.url}"
