import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import ChatRoom, Message
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse
from django.template.loader import render_to_string
import json
from django.utils import timezone

User = get_user_model()

@login_required
def chat_inbox(request):
    # Find all rooms where user is participant
    rooms = ChatRoom.objects.filter(
        Q(participant_1=request.user) | Q(participant_2=request.user)
    ).order_by('-updated_at')
    
    return render(request, 'chat/inbox.html', {'rooms': rooms})

@login_required
def chat_room(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    
    room = ChatRoom.objects.filter(
        (Q(participant_1=request.user) & Q(participant_2=other_user)) |
        (Q(participant_1=other_user) & Q(participant_2=request.user))
    ).first()

    if not room:
        room = ChatRoom.objects.create(participant_1=request.user, participant_2=other_user)

    # Load messages (exclude ones hidden by this user)
    chat_messages = room.messages.exclude(hidden_by=request.user).order_by('timestamp')
    
    # Mark unread messages from other user as read
    chat_messages.filter(sender=other_user, is_read=False).update(is_read=True)

    return render(request, 'chat/room.html', {
        'room': room, 
        'chat_messages': chat_messages, 
        'other_user': other_user
    })

@login_required
def contact_admin(request):
    """Finds a random admin and redirects to chat with them"""
    
    # 1. Try to find users with role='admin'
    admins = User.objects.filter(role='admin', is_active=True)
    
    # 2. Fallback: If no custom 'admin' role exists, look for Superusers
    if not admins.exists():
        admins = User.objects.filter(is_superuser=True, is_active=True)
    
    if admins.exists():
        # Pick one random admin
        selected_admin = random.choice(list(admins))
        
        # Redirect to the chat room with this specific admin ID
        return redirect('chat_room', user_id=selected_admin.id)
    else:
        # Error handling if no admins exist in the system
        messages.error(request, "No support agents are currently available.")
        return redirect('chat_inbox')
    
# --- AJAX API: SEND MESSAGE ---
@login_required
def send_message_api(request, room_id):
    if request.method == 'POST':
        room = get_object_or_404(ChatRoom, id=room_id)
        data = json.loads(request.body)
        content = data.get('content')
        
        if content:
            msg = Message.objects.create(room=room, sender=request.user, content=content)
            room.save() # update timestamp
            
            # Return HTML for the single message to append via JS
            return JsonResponse({
                'status': 'success', 
                'message_id': msg.id,
                'content': msg.content,
                'time': msg.timestamp.strftime("%H:%M")
            })
    return JsonResponse({'status': 'error'})

# --- NEW: CLEAR CHAT HISTORY ---
@login_required
def clear_chat_history(request, room_id):
    if request.method == 'POST':
        room = get_object_or_404(ChatRoom, id=room_id)
        # Check if user is in room
        if request.user not in [room.participant_1, room.participant_2]:
            return JsonResponse({'status': 'denied'})
            
        # Add user to hidden_by for ALL messages in this room
        msgs = room.messages.all()
        for m in msgs:
            m.hidden_by.add(request.user)
            
        return JsonResponse({'status': 'cleared'})
    return JsonResponse({'status': 'error'})

# --- UPDATED: MANAGE MESSAGE ---
@login_required
def manage_message(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        action = data.get('action')
        msg_id = data.get('message_id')
        msg = get_object_or_404(Message, id=msg_id)
        
        if action == 'delete_me':
            msg.hidden_by.add(request.user)
            return JsonResponse({'status': 'hidden'})
            
        if msg.sender != request.user:
            return JsonResponse({'status': 'denied'})

        if action == 'delete_everyone':
            msg.is_deleted_everyone = True
            msg.content = "🚫 This message was deleted."
            msg.save() # This updates 'updated_at' automatically
            return JsonResponse({'status': 'deleted', 'new_content': msg.content})
            
        elif action == 'edit':
            new_content = data.get('new_content')
            if new_content:
                msg.content = new_content
                msg.is_edited = True
                msg.save() # This updates 'updated_at' automatically
                return JsonResponse({'status': 'edited', 'new_content': new_content})

    return JsonResponse({'status': 'error'})

# --- UPDATED: GET UPDATES (Handles Real-time Edits) ---
@login_required
def get_updates(request, room_id):
    room = get_object_or_404(ChatRoom, id=room_id)
    
    # We now track "last_check" time instead of just ID
    last_check_str = request.GET.get('last_check', 0)
    
    # Get all messages updated or created after the last check
    # Note: Javascript sends timestamp in milliseconds, Python needs seconds
    try:
        last_check_ts = float(last_check_str)
        # Convert JS timestamp (ms) to Python datetime
        last_check_dt = timezone.datetime.fromtimestamp(last_check_ts, tz=timezone.utc)
    except:
        last_check_dt = timezone.now() - timezone.timedelta(seconds=10)

    # 1. New Messages (Created recently)
    new_msgs_qs = room.messages.filter(timestamp__gt=last_check_dt).exclude(hidden_by=request.user).order_by('timestamp')
    
    # 2. Updated Messages (Edited/Deleted recently but created long ago)
    updated_msgs_qs = room.messages.filter(updated_at__gt=last_check_dt, timestamp__lte=last_check_dt).exclude(hidden_by=request.user)

    new_data = []
    for msg in new_msgs_qs:
        new_data.append({
            'id': msg.id,
            'sender_id': msg.sender.id,
            'content': msg.content,
            'time': msg.timestamp.strftime("%H:%M"),
            'is_me': msg.sender == request.user,
            'is_deleted': msg.is_deleted_everyone
        })
        if msg.sender != request.user:
            msg.is_read = True
            msg.save()

    updated_data = []
    for msg in updated_msgs_qs:
        updated_data.append({
            'id': msg.id,
            'content': msg.content,
            'is_deleted': msg.is_deleted_everyone,
            'is_edited': msg.is_edited
        })

    return JsonResponse({
        'new_messages': new_data,
        'updated_messages': updated_data,
        'server_time': timezone.now().timestamp()
    })