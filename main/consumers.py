import asyncio
import json
from django.contrib.auth import get_user_model
from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async


class RAGConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        print("connected", event)
        # other_user = self.scope["url_route"]["kwargs"]["username"]
        # user = self.scope["user"]
        # self.user = user
        # thread_obj = await self.get_thread(user, other_user)
        # self.thread_obj = thread_obj
        # chat_room = f"thread_{thread_obj.id}"
        # self.chat_room = chat_room
        # await self.channel_layer.group_add(
        #     chat_room, 
        #     self.channel_name
        # )
        # print(thread_obj)
        # print(other_user, user)
        # print(user, thread_obj.id)
        await self.send({
            "type": "websocket.accept"
        })

    async def websocket_receive(self, event):
        print("receive", event)
        client_data = event.get('text', None)
        if client_data is not None:
            dict_data = json.loads(client_data)
            msg = dict_data.get("message")
            other_user = self.scope["url_route"]["kwargs"]["username"]
            user = self.scope["user"]
            username = "default"
            if user.is_authenticated:
                username = user.username
            await self.create_chat_message(msg)
            response = {
                "message": msg,
                "username": username,
            }

            await self.channel_layer.group_send(
                self.chat_room,
                {
                    "type": "chat.message",
                    "text": json.dumps(response)
                }
            )

    async def chat_message(self, event):
        await self.send(
            {
                "type": "websocket.send",
                "text": event["text"],
            }
        )

    async def websocket_disconnect(self, event):
        print("disconnected", event)


    @database_sync_to_async
    def get_thread(self, user, other_username):
        return Thread.objects.get_or_new(user, other_username)[0]
    
    @database_sync_to_async
    def create_chat_message(self, message):
        thread_obj=self.thread_obj
        user = self.scope["user"]
        ChatMessage.objects.create(thread=thread_obj, user=user, message=message)
        print("\nChat message saved\n")
        return 