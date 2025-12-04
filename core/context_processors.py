from .models import Notification

def user_notifications(request):
    if request.user.is_authenticated:
        # Get unread notifications
        notifs = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')
        return {'notifications': notifs, 'notification_count': notifs.count()}
    return {'notification_count': 0}