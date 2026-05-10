import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import ChatMessage, RentalRequest, CustomUser


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1. Grab the rental request ID directly from the URL
        self.request_id = self.scope['url_route']['kwargs']['request_id']

        # 2. Name the Redis channel exactly for this specific chat room
        self.room_group_name = f'chat_{self.request_id}'

        # 3. Add this connection to the Redis group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # 4. Accept the WebSocket connection!
        await self.accept()

    async def disconnect(self, close_code):
        # Remove the user from the Redis group when they close the tab
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from the frontend browser
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        sender_id = text_data_json['sender_id']

        # Save the message securely to Supabase
        saved_msg = await self.save_message(self.request_id, sender_id, message)

        # Blast the message through Redis to everyone in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender_id': sender_id,
                'is_system_update': False,  # Normal user messages are False
                'timestamp': saved_msg.created_at.strftime("%I:%M %p"),  # e.g., "02:30 PM"
            }
        )

    # Receive the broadcasted message from Redis and send it down to the user's screen
    async def chat_message(self, event):
        # THE FIX: Added is_system_update and new_price to the outgoing WebSocket payload
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'is_system_update': event.get('is_system_update', False),
            'new_price': event.get('new_price', None),
            'timestamp': event['timestamp']
        }))

    # We must use @sync_to_async because Django's database isn't naturally asynchronous yet
    @sync_to_async
    def save_message(self, request_id, sender_id, text):
        rental_request = RentalRequest.objects.get(id=request_id)
        sender = CustomUser.objects.get(id=sender_id)
        return ChatMessage.objects.create(
            rental_request=rental_request,
            sender=sender,
            text=text
        )