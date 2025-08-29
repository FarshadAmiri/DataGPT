import asyncio
import json
import threading
from django.contrib.auth import get_user_model
from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async
import chromadb
from transformers import TextIteratorStreamer
import torch
# from main.views import model, tokenizer
from main.models import Thread, ChatMessage, Document
from main.utilities.RAG import embedding_model_st, rerank_minilm, rerank_alibaba
from main.utilities.translation import translate_en_fa
from main.utilities.variables import *
from main.utilities.variables import *
from main.utilities.encryption import *
from main.utilities.helper_functions import remove_non_printable
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import aiohttp
from openai import OpenAI


class RAGConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        print("connected", event)
        self.user = self.scope["user"]
        try:
            await self._setup_vector_db()
            await self.get_history(history_size=history_size)
        except Exception as e:
            print(f"redirect to landing page - No chat thread with Vector DB detected yet: {e}")
            return
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
        global max_new_tokens
        username = self.user.username
        encrypted_message = dict_data.get("encrypted_message")
        encrypted_aes_key = dict_data.get("encrypted_aes_key")
        chat_mode = dict_data.get("chat_mode")  # "standard" or "rag"
        similarity_cutoff = float(dict_data.get("similarity_cutoff", 0.0))  # convert to float
        rerank_enabled = dict_data.get("rerank")
        temperature = float(dict_data.get("temperature", 0.7))  # convert to float
        
        # ---- Input validation ----
        temperature = temperature if (0.1 <= temperature <= 1.2) else 0.5

        # ---- Decrypt ----
        aes_key = decrypt_aes_key(encrypted_aes_key)
        query = decrypt_AES_ECB(encrypted_message, aes_key)
        query = remove_non_printable(query)
        print(f"\n\nquery: {query}\n\n")

        await self.create_chat_message(query, rag_response=False, source_nodes=None)

        # ---- Exceptional cases handling ----
        # Greetings:
        greetings = ["hi", "hello", "hey", "heey", "heeey", "سلام"]
        query = query.replace("!", "")
        query = query.replace("?", "")
        if query.lower() in greetings:
            max_new_tokens = 25
            chat_mode = "standard"

        # ---- Conversation history ----
        history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in self.history])
        print(f"\n\nhistory_text: {history_text}\n\n")


        # ---- RAG retrieval ----
        if chat_mode == "rag":
            extracted_query = self.keyword_extractor(query, llm_url, keyword_extractor_prompt)
            print(f"\n\nextracted_query: {extracted_query}\n\n")

            query_emb = embedding_model_st.encode(extracted_query).reshape(1, -1)
            results = self.collection.get(include=["documents", "embeddings"])
            chunk_texts = results["documents"]
            chunk_embs = np.array(results["embeddings"])
            similarities = cosine_similarity(query_emb, chunk_embs)[0]

            # Apply similarity cutoff BEFORE sorting
            filtered_indices = [i for i, sim in enumerate(similarities) if sim >= similarity_cutoff]
            print(f"\nFiltered {len(similarities) - len(filtered_indices)} chunks below cutoff {similarity_cutoff}")

            # Sort remaining ones by similarity
            sorted_indices = sorted(filtered_indices, key=lambda i: similarities[i], reverse=True)[:max_n_retreivals]

            # After computing similarities and filtering/sorting:
            source_nodes_dict = {}
            top_chunks = []
            top_chunks_with_scores = []  # new list to store chunk + similarity

            for idx, i in enumerate(sorted_indices):
                chunk_text = chunk_texts[i]
                sim_score = similarities[i]  # get similarity
                chunk_id = results["ids"][i]
                # print(f"\nchunk_id: {chunk_id}\n")
                doc_id = chunk_id.split("_")[0]
                try:
                    doc_id = int(doc_id)
                    doc_name = await self.get_doc_name(doc_id)
                except ValueError:
                    doc_name = f"#{idx+1} [Similarity: {sim_score:.3f}]"
                source_nodes_dict[doc_name] = chunk_text
                top_chunks.append(chunk_text)
                top_chunks_with_scores.append(f"[Similarity: {sim_score:.3f}]\n{chunk_text}")

            # If reranking is enabled
            if rerank_enabled and top_chunks:
                print(f"\nlen(top_chunks) before rerank: {len(top_chunks)}")
                
                original_mapping = dict(source_nodes_dict)
                
                # Rerank
                top_chunks = rerank_minilm(query=query, texts=top_chunks, threshold=rerank_score_threshold, return_scores=False)
                print(f"len(top_chunks) after rerank: {len(top_chunks)}\n")
                
                # Update source_nodes_dict
                new_source_nodes = {}
                new_top_chunks_with_scores = []
                for doc_name, chunk_text in original_mapping.items():
                    if chunk_text in top_chunks:
                        new_source_nodes[doc_name] = chunk_text
                        # find corresponding chunk with score
                        for s_chunk in top_chunks_with_scores:
                            if chunk_text in s_chunk:
                                new_top_chunks_with_scores.append(s_chunk)
                source_nodes_dict = new_source_nodes
                top_chunks_with_scores = new_top_chunks_with_scores

            # Build rag_contexts string including similarity scores
            rag_contexts = "\n\n".join(top_chunks_with_scores)
            # print(f"\nRAG Contexts with similarity scores:\n{rag_contexts}\n\n")

            if rag_contexts == "":
                rag_contexts = "No relevant context found."
            

        elif chat_mode == "standard":
            rag_contexts = None

        # print("self.history:\n", self.history)
        
        try:
            full_response = await self.stream_llm_response(llm_url, query, username, aes_key, temperature=temperature, 
                                                            chat_history=self.history, rag_contexts=rag_contexts, context_as_system=True)
        except Exception as e:
            print("Streaming error:", e)
            full_response = ""

        print("\n\nRESPONSE GENERATION COMPLETED\n\n")
        try:
            full_response = full_response.strip()
            if chat_mode=="rag":
                message_id = await self.create_chat_message(full_response, rag_response=True, source_nodes=json.dumps(source_nodes_dict))
            elif chat_mode=="standard":
                message_id = await self.create_chat_message(full_response, rag_response=True)

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

        # while loop.time() < end_time:
        while True:
            token = await loop.run_in_executor(None, get_next_token)
            if token is None:
                break
            yield token


    def build_payload(self, prompt, *, chat_history=None, rag_contexts=None, context_as_system=False, temperature=0.7):
        """
        Build payload for LLM request including chat history and RAG contexts
        """
        # Ensure defaults
        chat_history = chat_history or []
        rag_contexts = rag_contexts or []

        # Prepare context message from RAG results
        rag_text = "\n\n".join(rag_contexts) if rag_contexts else ""
        if rag_text:
            rag_message = {
                "role": "system" if context_as_system else "user",
                "content": f"Context information:\n{rag_text}"
            }
        else:
            rag_message = None

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that answers questions directly. "
                    "Do not add greetings or extra commentary."
                )
            },
            *chat_history
        ]
        if rag_message:
            messages.append(rag_message)

        messages.append({
            "role": "user",
            "content": prompt
        })

        payload = {
            "model": "Qwen/Qwen3-4B-AWQ",
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "top_p": 1.0,
            "top_k": 1,
            "max_tokens": 1024,
            "presence_penalty": 1.5,
            "chat_template_kwargs": {"enable_thinking": False}
        }
        return payload


    async def stream_llm_response(self, llm_url, prompt, username, aes_key,
                                temperature=0.7, chat_history=None, rag_contexts=None, context_as_system=False):
        """
        Stream response from LLM API and send over WebSocket in chunks
        """
        llm_url += "/chat/completions"
        payload = self.build_payload(
            prompt,
            chat_history=chat_history,
            rag_contexts=rag_contexts,
            context_as_system=context_as_system,
            temperature=temperature
        )

        headers = {"Content-Type": "application/json"}
        full_response = ""
        counter = 0

        async with aiohttp.ClientSession() as session:
            async with session.post(llm_url, json=payload, headers=headers) as resp:
                async for line_bytes in resp.content:
                    line = line_bytes.decode("utf-8").strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[len("data: "):].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data_json = json.loads(data_str)
                            chunk = data_json["choices"][0]["delta"].get("content", "")
                            if not chunk:
                                continue

                            full_response += chunk
                            counter += 1

                            if counter == 1:
                                await self.send({
                                    "type": "websocket.send",
                                    "text": json.dumps({
                                        "message": "",
                                        "username": username,
                                        "mode": "new"
                                    })
                                })

                            if stop_sequence in full_response:
                                full_response = full_response.split(stop_sequence)[0]
                                break

                            encrypted_chunk = encrypt_AES_ECB(chunk, aes_key).decode("utf-8")
                            await self.send({
                                "type": "websocket.send",
                                "text": json.dumps({
                                    "message": encrypted_chunk,
                                    "username": username,
                                    "mode": "continue"
                                })
                            })
                        except Exception as e:
                            print("Error decoding stream chunk:", e)
                            continue
        return full_response


    async def websocket_disconnect(self, event):
        print("disconnected", event)

    @database_sync_to_async
    def get_thread(self, chat_id):
        return Thread.objects.get(id=chat_id)
    

    @database_sync_to_async
    def get_history(self, history_size=3):
        if history_size <= 0:
            self.history = []
            return self.history

        chat_id = self.scope["url_route"]["kwargs"]["chat_id"]

        # Fetch up to history_size*2 messages (in case assistant/user pairs)
        messages_qs = (
            ChatMessage.objects
            .filter(thread_id=chat_id)
            .order_by("-timestamp")[: history_size * 2]
            .select_related("user")
        )

        if not messages_qs.exists():
            # No messages found
            self.history = []
            return self.history

        # Reverse to get oldest → newest
        messages = list(reversed(messages_qs))

        history = []
        for msg in messages:
            role = "assistant" if msg.rag_response else "user"
            history.append({
                "role": role,
                "content": msg.message or ""   # prevent NoneType errors
            })

        # Ensure at most `history_size` exchanges are stored
        self.history = history[-history_size * 2 :]
        return self.history


    @database_sync_to_async
    def create_chat_message(self, message, rag_response, source_nodes=None):
        if source_nodes==None:
            return ChatMessage.objects.create(thread=self.thread, user=self.scope["user"], message=message, rag_response=rag_response).id
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
        try:
            contexts = json.loads(contexts)
        except:
            contexts = {}
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

    @database_sync_to_async
    def get_doc_name(self, doc_id):
        return Document.objects.get(id=doc_id).name


    def keyword_extractor(self, text, llm_url, keyword_extractor_prompt):
        client = OpenAI(base_url=llm_url, api_key="not-needed")
        prompt = f"{keyword_extractor_prompt}User: {text}\nKeywords:"

        resp = client.chat.completions.create(
            model="Qwen/Qwen3-4B-AWQ",
            messages=[
                {"role": "system", "content": "You are a keyword extraction assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=30,
            extra_body={  # 👇 disables thinking traces
                "chat_template_kwargs": {"enable_thinking": False}
            }
        )

        generated_text = resp.choices[0].message.content.strip()

        if "Keywords:" in generated_text:
            extracted_keywords = generated_text.split("Keywords:")[-1].strip()
        else:
            extracted_keywords = generated_text

        print("Extracted Keywords:", extracted_keywords)
        return extracted_keywords


