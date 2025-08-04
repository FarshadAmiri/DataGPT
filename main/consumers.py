import asyncio
import json
import threading
from django.contrib.auth import get_user_model
from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async
import chromadb
from transformers import TextIteratorStreamer
import torch
from main.views import model, tokenizer
from main.models import Thread, ChatMessage, Document
from main.utilities.RAG import embedding_model_st
from main.utilities.translation import translate_en_fa
from main.utilities.variables import keyword_extractor_prompt
from main.utilities.encryption import *
from main.utilities.helper_functions import remove_non_printable
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


class RAGConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        print("connected", event)
        self.user = self.scope["user"]
        await self._setup_vector_db()
        await self.send({"type": "websocket.accept"})

    async def _setup_vector_db(self):
        chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        thread = await self.get_thread(chat_id=chat_id)
        self.thread = thread
        self.db = chromadb.PersistentClient(path=thread.loc)
        self.collection = self.db.get_or_create_collection("default")

    async def websocket_receive(self, event):
        client_data = event.get('text', None)
        if not client_data:
            return
        dict_data = json.loads(client_data)
        mode = dict_data.get("mode")
        if mode == "translation":
            await self._handle_translation(dict_data)
        elif mode == "context":
            await self._handle_context(dict_data)
        else:
            await self._handle_chat(dict_data)

    async def _handle_chat(self, dict_data):
        username = self.user.username
        encrypted_message = dict_data.get("encrypted_message")
        encrypted_aes_key = dict_data.get("encrypted_aes_key")
        aes_key = decrypt_aes_key(encrypted_aes_key)
        msg = decrypt_AES_ECB(encrypted_message, aes_key)
        msg = remove_non_printable(msg)
        print(f"msg: {msg}")

        await self.create_chat_message(msg, rag_response=False, source_nodes=None)

        # Get embedding and retrieve relevant chunks
        extracted_query = self.keyword_extractor(msg, model, tokenizer, keyword_extractor_prompt)
        print(f"\n\nextracted_query: {extracted_query}\n\n")
        query_emb = embedding_model_st.encode(extracted_query).reshape(1, -1)
        results = self.collection.get(include=["documents", "embeddings"])
        chunk_texts = results["documents"]
        chunk_embs = np.array(results["embeddings"])
        similarities = cosine_similarity(query_emb, chunk_embs)[0]
        sorted_indices = np.argsort(similarities)[::-1][:3]
        # top_chunks = [chunk_texts[i] for i in sorted_indices]
        # top_text = "\n\n".join(top_chunks)
        source_nodes_dict = {}
        top_chunks = []
        for i in sorted_indices:
            chunk_text = chunk_texts[i]
            chunk_id = results["ids"][i]  # e.g., "5_0"
            doc_id = chunk_id.split("_")[0]
            try:
                doc_id = int(doc_id)
                doc_name = await self.get_doc_name(doc_id)
            except ValueError:
                doc_name = "Unknown document"
            source_nodes_dict[doc_name] = chunk_text
            top_chunks.append(chunk_text)
        print(f"top_chunks: {top_chunks}")
        top_text = "\n\n".join(top_chunks)


        # Construct prompt
        system_prompt = (
            "You are a helpful assistant. Base your answer on the following context."
        )
        prompt = f"{system_prompt}\n\nContext:\n{top_text}\n\nUser: {msg}\nAssistant:"

        # Tokenize and create streamer
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        gen_kwargs = {
            "inputs": inputs["input_ids"],
            "streamer": streamer,
            "max_new_tokens": 2048,
            "temperature": 0.7,  #0.0 –0.3 : deterministic, safe |  0.7: balanced.   temperature > 1.0: creative, possibly chaotic.
            "do_sample": True,  # Enables randomness when picking tokens. Should be True if temperature > 0.
            "top_p": 0.9,    # Nucleus sampling — limits to a dynamic top % of tokens. Usually 0.9.
            "pad_token_id": tokenizer.eos_token_id,
        }

        generation_thread = threading.Thread(target=model.generate, kwargs=gen_kwargs)
        generation_thread.start()

        full_response = ""
        counter = 0
        try:
            async for chunk in self._stream_response(streamer, timeout=20):  # ⏱ Set timeout to avoid hanging
                if counter == 0:
                    await self.send({
                        "type": "websocket.send",
                        "text": json.dumps({"message": "", "username": username, "mode": "new"})
                    })
                encrypted_chunk = encrypt_AES_ECB(chunk, aes_key).decode('utf-8')
                await self.send({
                    "type": "websocket.send",
                    "text": json.dumps({"message": encrypted_chunk, "username": username, "mode": "continue"})
                })
                full_response += chunk
                counter += 1
        except Exception as e:
            print("Streaming error:", e)

        print("\n\nRESPONSE GENERATION COMPLETED\n\n")
        try:
            # message_id = await self.create_chat_message(full_response, rag_response=True, source_nodes=json.dumps({}))
            message_id = await self.create_chat_message(full_response, rag_response=True, source_nodes=json.dumps(source_nodes_dict))

            await self.send({
                "type": "websocket.send",
                "text": json.dumps({"message_id": message_id, "mode": "last"})
            })
        except Exception as e:
            print("Failed to create message:", e)

    async def _stream_response(self, streamer, timeout=20):
        loop = asyncio.get_event_loop()
        end_time = loop.time() + timeout

        def get_next_token():
            try:
                return next(streamer)
            except StopIteration:
                return None

        while loop.time() < end_time:
            token = await loop.run_in_executor(None, get_next_token)
            if token is None:
                break
            yield token

    async def websocket_disconnect(self, event):
        print("disconnected", event)

    @database_sync_to_async
    def get_thread(self, chat_id):
        return Thread.objects.get(id=chat_id)

    @database_sync_to_async
    def create_chat_message(self, message, rag_response, source_nodes):
        return ChatMessage.objects.create(thread=self.thread, user=self.scope["user"], message=message, rag_response=rag_response, source_nodes=source_nodes).id

    async def _handle_translation(self, dict_data):
        message_id = dict_data.get("message_id")
        translation_task = await self.get_message(message_id)
        encrypted_aes_key = dict_data.get("encrypted_aes_key")
        aes_key = decrypt_aes_key(encrypted_aes_key)
        persian_translation = translate_en_fa(translation_task)
        encrypted_persian_translation = encrypt_AES_ECB(persian_translation, aes_key).decode('utf-8')
        await self.send({
            "type": "websocket.send",
            "text": json.dumps({
                "encrypted_persian_translation": encrypted_persian_translation,
                "message_id": message_id,
                "mode": "translation",
            }),
        })

    @database_sync_to_async
    def get_message(self, message_id):
        return ChatMessage.objects.get(id=message_id).message

    async def _handle_context(self, dict_data):
        message_id = dict_data.get("message_id")
        contexts = await self.get_context(message_id)
        encrypted_aes_key = dict_data.get("encrypted_aes_key")
        aes_key = decrypt_aes_key(encrypted_aes_key)
        contexts = json.loads(contexts)
        encrypted_contexts = {
            encrypt_AES_ECB(k, aes_key).decode('utf-8'): encrypt_AES_ECB(v, aes_key).decode('utf-8')
            for k, v in contexts.items()
        }
        await self.send({
            "type": "websocket.send",
            "text": json.dumps({
                "mode": "context",
                "message_id": message_id,
                "encrypted_contexts": encrypted_contexts,
            }),
        })

    @database_sync_to_async
    def get_context(self, message_id):
        return ChatMessage.objects.get(id=message_id).source_nodes

    # @database_sync_to_async
    # def get_doc_name(self, node_id):
    #     doc_id = node_id.split("_")[0]
    #     doc_name = Document.objects.get(id=doc_id).name
    #     return doc_name

    @database_sync_to_async
    def get_doc_name(self, doc_id):
        return Document.objects.get(id=doc_id).name

    def keyword_extractor(self, text, model, tokenizer, keyword_extractor_prompt):
        prompt = f"{keyword_extractor_prompt}User: {text}\nKeywords:"
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=30,
                temperature=0.7,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )
        generated_text = tokenizer.decode(output[0], skip_special_tokens=True)
        extracted_keywords = generated_text.split("Keywords:")[-1].strip()
        print("Extracted Keywords:", extracted_keywords)
        return extracted_keywords
