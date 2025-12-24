import asyncio
import json
import threading
import os
import re
from typing import Dict, Tuple
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
from main.utilities.encryption import *
from main.utilities.helper_functions import remove_non_printable
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import aiohttp
from openai import OpenAI
import requests


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
        chat_mode = dict_data.get("chat_mode")  # "standard", "rag", or "database"
        similarity_cutoff = float(dict_data.get("similarity_cutoff", 0.0))  # convert to float
        rerank_enabled = dict_data.get("rerank")
        temperature = float(dict_data.get("temperature", 0.7))  # convert to float

        try:
            await self.get_history(history_size=history_size)
        except Exception as e:
            print(f"Problem loading chat history: {e}")
            return
        
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
        source_nodes_dict = {}
        if chat_mode == "rag":
            extracted_query = self.keyword_extractor(query, llm_url, keyword_extractor_prompt)
            print(f"\n\nextracted_query: {extracted_query}\n\n")

            query_emb = embedding_model_st.encode(extracted_query).reshape(1, -1)
            results = self.collection.get(include=["documents", "embeddings"])
            chunk_texts = results.get("documents", [])
            chunk_embs = np.array(results.get("embeddings", []))

            top_chunks = []
            top_chunks_with_scores = []

            # ✅ Only compute similarities if there are embeddings
            if len(chunk_embs) > 0:
                similarities = cosine_similarity(query_emb, chunk_embs)[0]

                # Apply similarity cutoff BEFORE sorting
                filtered_indices = [i for i, sim in enumerate(similarities) if sim >= similarity_cutoff]
                print(f"\nFiltered {len(similarities) - len(filtered_indices)} chunks below cutoff {similarity_cutoff}")

                # Sort remaining ones by similarity
                sorted_indices = sorted(filtered_indices, key=lambda i: similarities[i], reverse=True)[:max_n_retreivals]

                # Collect top chunks with similarity
                for idx, i in enumerate(sorted_indices):
                    chunk_text = chunk_texts[i]
                    sim_score = similarities[i]
                    chunk_id = results["ids"][i]
                    doc_id = chunk_id.split("_")[0]
                    try:
                        doc_id = int(doc_id)
                        doc_name = await self.get_doc_name(doc_id)
                    except ValueError:
                        doc_name = f"#{idx+1} [Similarity: {sim_score:.3f}]"
                    source_nodes_dict[doc_name] = chunk_text
                    top_chunks.append(chunk_text)
                    top_chunks_with_scores.append(f"[Similarity: {sim_score:.3f}]\n{chunk_text}")
            else:
                # No embeddings found — continue with empty context
                print("No documents indexed — continuing without context.")

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
            

        elif chat_mode == "database":
            # Database-powered mode
            rag_contexts_str, source_nodes_dict = await self._handle_database_query(query)
            # Wrap in list since build_payload expects a list
            rag_contexts = [rag_contexts_str] if rag_contexts_str else []
            
        elif chat_mode == "standard":
            rag_contexts = None

        # print("self.history:\n", self.history)
        
        # For database mode, mark it so we can prioritize database results over history
        is_database_mode = (chat_mode == "database")
        
        try:
            full_response = await self.stream_llm_response(llm_url, query, username, aes_key, temperature=temperature, 
                                                            chat_history=self.history, rag_contexts=rag_contexts, 
                                                            context_as_system=True, is_database_mode=is_database_mode)
        except Exception as e:
            print("Streaming error:", e)
            full_response = ""

        print("\n\nRESPONSE GENERATION COMPLETED\n\n")
        try:
            full_response = full_response.strip()
            if chat_mode == "rag":
                message_id = await self.create_chat_message(full_response, rag_response=True, source_nodes=json.dumps(source_nodes_dict))
            elif chat_mode == "database":
                message_id = await self.create_chat_message(full_response, rag_response=True, source_nodes=json.dumps(source_nodes_dict))
            elif chat_mode == "standard":
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


    def build_payload(self, prompt, *, chat_history=None, rag_contexts=None, context_as_system=False, temperature=0.7, is_database_mode=False):
        global model_name
        """
        Build payload for LLM request including chat history and RAG contexts
        For database mode, prioritizes fresh query results over potentially wrong chat history
        """
        # Ensure defaults
        chat_history = chat_history or []
        rag_contexts = rag_contexts or []

        # Prepare context message from RAG/Database results
        rag_text = "\n\n".join(rag_contexts) if rag_contexts else ""
        
        # Detect if this is database/Excel results
        # For SQL: look for SELECT, Columns:, COUNT(*)
        # For Pandas/Excel: check if is_database_mode is True (since it's set for both database and excel)
        has_database_results = (
            "SELECT" in rag_text or "Columns:" in rag_text or "COUNT(*)" in rag_text or
            "dfs[" in rag_text or  # Pandas DataFrame query
            is_database_mode  # Trust the flag when explicitly set
        )
        
        if is_database_mode and has_database_results:
            # DATABASE MODE: Fresh query results take ABSOLUTE PRIORITY
            # Limit chat history to prevent accumulation of wrong answers
            # Only keep last 2 exchanges (4 messages) to maintain context but minimize false info
            limited_history = chat_history[-4:] if len(chat_history) > 4 else chat_history
            
            # Extract the actual numeric result if present
            result_number = None
            if "**RESULT:" in rag_text:
                import re
                match = re.search(r'\*\*RESULT:\s*(\d+)\*\*', rag_text)
                if match:
                    result_number = match.group(1)
            
            messages = [
                {
                    "role": "system",
                    "content": (
                        """You are an AI assistant that answers questions using database/Excel query results.
                        
                        ABSOLUTE PRIORITY RULES - THESE OVERRIDE EVERYTHING:
                        1. The database/Excel query results provided below are the ONLY source of truth
                        2. IGNORE any conflicting information from chat history
                        3. If chat history says "5 people" but query shows "2 people", use "2 people"
                        4. NEVER use numbers, names, or data from previous messages if query provides fresh data
                        5. Chat history is ONLY for understanding context, NOT for data values
                        6. Trust ONLY the query results - they are authoritative and current
                        7. Do NOT make up, hallucinate, or invent any data
                        8. If query result shows 14, the answer is 14, not any other number
                        9. When query returns a number, that IS the answer - state it directly
                        10. Excel/Pandas queries return actual data from the files - trust them completely
                        11. Look for **RESULT:** in the query results - that is the direct answer
                        
                        Formatting:
                        - Use emojis in titles and headings
                        - Be clear and direct
                        - Show the actual data from the query
                        - If the query result is a number, state it in your answer"""
                    )
                },
                # Put database results FIRST as a system message (highest priority)
                {
                    "role": "system",
                    "content": f"""CURRENT QUERY RESULTS (USE THIS DATA - IT IS THE TRUTH):
{rag_text}

⚠️ CRITICAL: The data above is fresh from the database/Excel file RIGHT NOW. Use ONLY this data for your answer.
If previous chat messages have different numbers or data, IGNORE them - they may be outdated or wrong.
The query results above are the authoritative source. If it says "14", your answer MUST include "14".
{'THE ANSWER IS: ' + result_number if result_number else ''}"""
                },
                # Then add limited chat history (for context only)
                *limited_history,
                # Finally the user's current question with INJECTED ANSWER if we have it
                {
                    "role": "user",
                    "content": f"{prompt}\n\n{'IMPORTANT: The answer from the query is: ' + result_number + '. Use this number in your response.' if result_number else 'Reminder: Use ONLY the database results provided above. Ignore any conflicting data from chat history.'}"
                }
            ]
        else:
            # REGULAR MODE (RAG or Standard): Original behavior
            if rag_text:
                context_prefix = "Context information:"
                rag_message = {
                    "role": "system" if context_as_system else "user",
                    "content": f"{context_prefix}\n{rag_text}\n\nIMPORTANT: Answer using ONLY the data above. Do not add, modify, or invent any data."
                }
            else:
                rag_message = None

            messages = [
                {
                    "role": "system",
                    "content": (
                        """You are an AI assistant that answers questions directly and honestly.
                        
                        CRITICAL RULES:
                        1. ONLY use information from the provided context - NEVER make up or hallucinate data
                        2. If context shows database results, use ONLY those exact results
                        3. Do NOT invent, assume, or fabricate any data not in the context
                        4. If you don't have enough information, say so clearly
                        5. Be honest about any errors or limitations
                        6. Always use emojis in titles and headings to make it engaging
                        7. Do not add greetings or extra commentary
                        8. Be consistent and accurate
                        
                        When presenting database results:
                        - Show only the data provided in the context
                        - Do not make up additional rows or values
                        - If filters were applied, respect them exactly"""
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
            # "model": "/home/farshad/models/Qwen3-4B-AWQ",
            "model": model_name,
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
                                temperature=0.7, chat_history=None, rag_contexts=None, context_as_system=False, is_database_mode=False):
        """
        Stream response from LLM API and send over WebSocket in chunks
        """
        llm_url += "/chat/completions"
        payload = self.build_payload(
            prompt,
            chat_history=chat_history,
            rag_contexts=rag_contexts,
            context_as_system=context_as_system,
            temperature=temperature,
            is_database_mode=is_database_mode
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
        global model_name
        endpoint = llm_url.rstrip("/") + "/chat/completions"

        messages = [
            {"role": "system", "content": "You are a keyword extraction assistant."},
            {"role": "user", "content": f"{keyword_extractor_prompt}User: {text}\nKeywords:"}
        ]
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 30,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}
        }

        headers = {"Content-Type": "application/json"}

        resp = requests.post(endpoint, json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Keyword extractor failed {resp.status_code}: {resp.text}")

        data = resp.json()
        generated_text = data["choices"][0]["message"]["content"].strip()

        if "Keywords:" in generated_text:
            extracted_keywords = generated_text.split("Keywords:")[-1].strip()
        else:
            extracted_keywords = generated_text

        print("Extracted Keywords:", extracted_keywords)
        return extracted_keywords

    async def _handle_database_query(self, user_question: str, max_retries: int = 3) -> Tuple[str, Dict[str, str]]:
        """
        Handle database-powered queries with retry logic
        Returns (formatted_results, source_nodes_dict) where source_nodes_dict contains queries and results
        """
        from main.utilities.database_utils import (
            generate_database_query, execute_sql_query, execute_mongodb_query,
            execute_pandas_query, format_query_results
        )
        from main.utilities.variables import llm_url
        
        # Get collection information
        collection = await self.get_base_collection()
        
        if not collection:
            return "Error: No database collection associated with this thread.", {}
        
        collection_type = collection.collection_type
        
        if collection_type not in ['database', 'excel']:
            return "Error: This collection is not database-backed.", {}
        
        # Get schema analysis
        schema_analysis = collection.db_schema_analysis
        db_type = collection.db_type if collection_type == 'database' else 'excel'
        
        if not schema_analysis:
            return "Error: No schema analysis available for this database.", {}
        
        # Track all queries and results
        source_nodes_dict = {}
        query_counter = 1
        previous_error = None  # Track error from previous attempt
        
        # Generate and execute query with retry logic
        for attempt in range(max_retries):
            try:
                print(f"\n[Attempt {attempt + 1}/{max_retries}] Generating database query...")
                
                # Generate query using LLM, passing previous error if any
                query = await asyncio.get_event_loop().run_in_executor(
                    None,
                    generate_database_query,
                    user_question,
                    schema_analysis,
                    db_type,
                    llm_url,
                    self.history,
                    previous_error
                )
                
                if not query:
                    if attempt < max_retries - 1:
                        continue
                    return "Error: Failed to generate query for your question.", source_nodes_dict
                
                print(f"Generated query: {query}")
                
                # Store the query in source_nodes_dict
                query_label = f"Query #{query_counter}" if query_counter > 1 else "Query"
                source_nodes_dict[query_label] = query
                
                # Execute query based on database type
                if collection_type == 'database':
                    if db_type in ['sqlite', 'mysql', 'postgresql']:
                        success, result = await asyncio.get_event_loop().run_in_executor(
                            None,
                            execute_sql_query,
                            db_type,
                            collection.db_connection_string,
                            query
                        )
                    elif db_type == 'mongodb':
                        # Parse query string to dict
                        try:
                            import ast
                            query_dict = ast.literal_eval(query)
                            # Extract collection name from query or use default
                            # For now, we'll need to parse this from the query
                            success, result = await asyncio.get_event_loop().run_in_executor(
                                None,
                                execute_mongodb_query,
                                collection.db_connection_string,
                                "default",  # TODO: Extract collection name from query
                                query_dict
                            )
                        except Exception as e:
                            success = False
                            result = f"Failed to parse MongoDB query: {str(e)}"
                    else:
                        success = False
                        result = f"Unsupported database type: {db_type}"
                
                elif collection_type == 'excel':
                    file_paths = collection.excel_file_paths or []
                    success, result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        execute_pandas_query,
                        file_paths,
                        query
                    )
                
                if success:
                    # Check if result is empty/zero for Excel queries - might need data inspection
                    should_inspect_data = False
                    if collection_type == 'excel':
                        if isinstance(result, (int, float)) and result == 0:
                            should_inspect_data = True
                        elif isinstance(result, list) and len(result) == 0:
                            should_inspect_data = True
                    
                    # If Excel query returned 0, inspect the data to find similar values
                    if should_inspect_data and attempt == 0:  # Only on first attempt
                        print("[Data Inspection] Query returned 0, checking for similar values...")
                        
                        # Send a message to user that we're inspecting data
                        await self.send({
                            "type": "websocket.send",
                            "text": json.dumps({
                                "message": "🔍 Analyzing data to find relevant values...",
                                "username": "system",
                                "mode": "status"
                            })
                        })
                        
                        # Extract column name from query (look for patterns like ['ColumnName'])
                        column_match = re.search(r"\['(\w+)'\]\s*==", query)
                        if column_match:
                            column_name = column_match.group(1)
                            print(f"[Data Inspection] Extracting unique values for column: {column_name}")
                            
                            # Get the DataFrame key from schema
                            file_paths_list = collection.excel_file_paths or []
                            if file_paths_list:
                                # Extract filename and construct DataFrame key
                                first_file = file_paths_list[0]
                                file_base = os.path.splitext(os.path.basename(first_file))[0]
                                df_key = f"{file_base}_Sheet1"  # Assuming Sheet1 for now
                                
                                # Query to get unique values for that column
                                inspection_query = f"result = dfs['{df_key}']['{column_name}'].unique().tolist()"
                                
                                try:
                                    inspect_success, unique_values = await asyncio.get_event_loop().run_in_executor(
                                        None,
                                        execute_pandas_query,
                                        file_paths_list,
                                        inspection_query
                                    )
                                    
                                    if inspect_success and unique_values:
                                        print(f"[Data Inspection] Found unique values: {unique_values}")
                                        
                                        # Add inspection results to context
                                        inspection_info = f"\n\n📊 DATA INSPECTION:\nThe column '{column_name}' contains these unique values: {unique_values}\n"
                                        inspection_info += f"Your query searched for a value that doesn't exist. Try one of the actual values listed above."
                                        
                                        source_nodes_dict["Data Inspection"] = f"Column '{column_name}' unique values: {unique_values}"
                                        
                                        # Add to previous_error so next attempt knows about available values
                                        previous_error = f"Query returned 0 results.\n\nAvailable values in '{column_name}' column: {unique_values}\n\nPlease modify the query to use one of these exact values."
                                        query_counter += 1
                                        
                                        # Continue to retry with this information
                                        continue
                                except Exception as inspect_error:
                                    print(f"[Data Inspection] Failed: {inspect_error}")
                    
                    # Format results for LLM to use
                    formatted_results = format_query_results(result, db_type)
                    
                    # Store raw results in source_nodes_dict
                    result_label = f"Raw Result #{query_counter}" if query_counter > 1 else "Raw Result"
                    
                    # Convert result to string format for display
                    if db_type in ['sqlite', 'mysql', 'postgresql']:
                        # Format SQL results as table
                        if isinstance(result, dict) and 'columns' in result and 'rows' in result:
                            raw_display = f"Columns: {', '.join(result['columns'])}\n\n"
                            raw_display += "Rows:\n"
                            for row in result['rows'][:50]:  # Limit to first 50 rows for display
                                raw_display += str(row) + "\n"
                            if len(result['rows']) > 50:
                                raw_display += f"\n... ({len(result['rows']) - 50} more rows)"
                    elif db_type == 'mongodb':
                        raw_display = json.dumps(result, indent=2)[:2000]  # Limit to 2000 chars
                    else:  # Excel/Pandas
                        raw_display = str(result)[:2000]  # Limit to 2000 chars
                    
                    source_nodes_dict[result_label] = raw_display
                    
                    print(f"Query executed successfully. Results:\n{formatted_results[:500]}...")
                    return formatted_results, source_nodes_dict
                else:
                    print(f"Query execution failed: {result}")
                    # Store failed query info
                    error_label = f"Error (Attempt {attempt + 1})"
                    source_nodes_dict[error_label] = f"Query: {query}\n\nError: {result}"
                    
                    # Store error for next attempt
                    previous_error = f"Query: {query}\nError: {result}"
                    query_counter += 1
                    
                    if attempt < max_retries - 1:
                        # Continue to next attempt with error context
                        continue
                    return f"Error executing query after {max_retries} attempts: {result}", source_nodes_dict
            
            except Exception as e:
                print(f"Exception in database query handling: {e}")
                error_label = f"Exception (Attempt {attempt + 1})"
                source_nodes_dict[error_label] = str(e)
                
                # Store exception for next attempt
                previous_error = f"Exception: {str(e)}"
                query_counter += 1
                if attempt < max_retries - 1:
                    continue
                return f"Error: {str(e)}", source_nodes_dict
        
        return "Error: Failed to execute database query after multiple attempts.", source_nodes_dict

    @database_sync_to_async
    def get_base_collection(self):
        """Get the base collection for the current thread"""
        from main.models import Collection
        if self.thread.base_collection:
            return self.thread.base_collection
        return None




