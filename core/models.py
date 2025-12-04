from django.db import models
from django.conf import settings

# --- NOTIFICATION SYSTEM ---
class Notification(models.Model):
    TYPES = [
        ('order', 'Order Update'),
        ('message', 'New Message'),
        ('alert', 'System Alert')
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=TYPES, default='alert')
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True, null=True) # Where clicking takes you
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notify {self.recipient}: {self.message}"
