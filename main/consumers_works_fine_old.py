import asyncio
import json
from django.contrib.auth import get_user_model
from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async
import chromadb
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from llama_index.vector_stores import ChromaVectorStore
from llama_index.storage.storage_context import StorageContext
from llama_index.prompts.prompts import SimpleInputPrompt
from llama_index.llms import HuggingFaceLLM
from llama_index.embeddings import LangchainEmbedding
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from llama_index import VectorStoreIndex, ServiceContext, set_global_service_context, get_response_synthesizer
from llama_index.retrievers import VectorIndexRetriever
from llama_index.query_engine import RetrieverQueryEngine
from llama_index.postprocessor import SimilarityPostprocessor
from main.views import model, tokenizer, streamer, device
from main.models import Thread, ChatMessage, Document
from main.utilities.RAG import embedding_model_st, embedding_model_st2
from main.utilities.translation import translate_en_fa, translate_fa_en, detect_language
from main.utilities.variables import system_prompt, query_wrapper_prompt, keyword_extractor_prompt
from main.utilities.encryption import *
from main.utilities.helper_functions import remove_non_printable


class RAGConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        print("connected", event)
        self.user = self.scope["user"]
        await self._setup_vector_db()
        await self.send({"type": "websocket.accept"})

    async def _setup_vector_db(self):
        """Initializes vector DB and stores index for dynamic query engine creation."""
        try:
            chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
            thread = await self.get_thread(chat_id=chat_id)
            self.thread = thread
            print(f"\nthread.loc: {thread.loc}\n")
            db = chromadb.PersistentClient(path=thread.loc)
            chroma_collection = db.get_or_create_collection("default", embedding_function=embedding_model_st2)
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
        except Exception as e:
            print(f"Vector DB setup failed: {e}")
            return

        # System prompt for LLM
        sys_prompt = (
            """
            You are a helpful, respectful and honest assistant. Always answer as
            helpfully as possible, while being safe.
            If a question does not make any sense, or is not factually coherent, explain
            why instead of answering something not correct. If you don't know the answer
            to a question, please don't share false information.
            Try to be exact in information and numbers you tell.
            Your goal is to provide answers completely based on the information provided
            and if you use yourown knowledge please inform the user.
            and it is important to respond as breifly as possible.
            """
        )
        query_prompt = SimpleInputPrompt("{query_str}  ")
        llm = HuggingFaceLLM(
            context_window=4096,
            max_new_tokens=512,
            system_prompt=sys_prompt,
            query_wrapper_prompt=query_prompt,
            model=model,
            tokenizer=tokenizer,
        )
        service_context = ServiceContext.from_defaults(
            chunk_size=1024,
            chunk_overlap=20,
            llm=llm,
            embed_model=embedding_model_st,
        )
        set_global_service_context(service_context)
        try:
            self.index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        except Exception as e:
            print(f"Query engine setup failed: {e}")

    def _build_query_engine(self, index, top_k, cutoff):
        retriever = VectorIndexRetriever(index=index, similarity_top_k=top_k)
        response_synthesizer = get_response_synthesizer(streaming=True)
        return RetrieverQueryEngine(
            retriever=retriever,
            response_synthesizer=response_synthesizer,
            node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=cutoff)],
        )

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

    async def _handle_translation(self, dict_data):
        message_id = dict_data.get("message_id")
        translation_task = await self.get_message(message_id)
        encrypted_aes_key = dict_data.get("encrypted_aes_key")
        aes_key = decrypt_aes_key(encrypted_aes_key)
        persian_translation = self.translate_to_fa(translation_task)
        encrypted_persian_translation = encrypt_AES_ECB(persian_translation, aes_key).decode('utf-8')
        response_dict = {
            "encrypted_persian_translation": encrypted_persian_translation,
            "message_id": message_id,
            "mode": "translation",
        }
        await self.send({
            "type": "websocket.send",
            "text": json.dumps(response_dict),
        })

    async def _handle_context(self, dict_data):
        message_id = dict_data.get("message_id")
        contexts = await self.get_context(message_id)
        encrypted_aes_key = dict_data.get("encrypted_aes_key")
        aes_key = decrypt_aes_key(encrypted_aes_key)
        contexts = json.loads(contexts)
        encrypted_contexts = {}
        for context_key in contexts:
            encrypted_context_key = encrypt_AES_ECB(context_key, aes_key).decode('utf-8')
            encrypted_contexts[encrypted_context_key] = encrypt_AES_ECB(contexts[context_key], aes_key).decode('utf-8')
        print(f"\ncontexts type: {type(contexts)}\n")
        print(f"\ncontexts: {contexts}\n")
        response_dict = {
            "mode": "context",
            "message_id": message_id,
            "encrypted_contexts": encrypted_contexts,
        }
        await self.send({
            "type": "websocket.send",
            "text": json.dumps(response_dict),
        })

    async def _handle_chat(self, dict_data):
        username = self.user.username
        encrypted_message = dict_data.get("encrypted_message")
        encrypted_aes_key = dict_data.get("encrypted_aes_key")
        aes_key = decrypt_aes_key(encrypted_aes_key)
        msg = decrypt_AES_ECB(encrypted_message, aes_key)
        msg = remove_non_printable(msg)
        print(f"msg: {msg}")
        await self.create_chat_message(msg, rag_response=False, source_nodes=None)
        print("msg: ", msg)
        full_response = ""

        # Get similarity_cutoff from client, default to 0.35 if not provided
        similarity_cutoff = dict_data.get("similarity_cutoff", 0.35)

        print(f"\ndict_data: {dict_data}\n")
        print(f"\nsimilarity_cutoff: {similarity_cutoff}\n")
        print(f"\ntype(similarity_cutoff): {type(similarity_cutoff)}\n")

        # Always use top_k=3
        query_engine_k3 = self._build_query_engine(self.index, top_k=3, cutoff=similarity_cutoff)
        query_engine_k2 = self._build_query_engine(self.index, top_k=2, cutoff=similarity_cutoff)
        query_engine_k1 = self._build_query_engine(self.index, top_k=5, cutoff=0.01)

        keywords = self.keyword_extractor(msg, model, tokenizer, keyword_extractor_prompt)
        print(f"\nkeywords: {keywords}\n")
        
        response = query_engine_k3.query(keywords)
        print(f"\nquery_engine_k3: {response.source_nodes}\n")

        # Query with fallback to less strict engines
        if len(response.source_nodes) == 0:
            response = query_engine_k2.query(msg)
            print(f"\nquery_engine_k2: {response.source_nodes}\n")
            if len(response.source_nodes) == 0:
                response = query_engine_k1.query(msg)
                print(f"\nquery_engine_k1: {response.source_nodes}\n")
                full_response = "No relevant information was found in the document sources; here is the LLM response generated to address your question:\n"
                full_response = ""

        # No fallback to other cutoffs, just use what client sent
        source_nodes = response.source_nodes
        source_nodes_dict = {}
        for node in source_nodes:
            metadata = node.node.relationships
            key = list(metadata.keys())[0]
            node_id = metadata[key].node_id
            doc_name = await self.get_doc_name(node_id)
            node_text = node.text
            source_nodes_dict[doc_name] = node_text
        source_nodes_json = json.dumps(source_nodes_dict)
        response_generator = self.query_engine_streamer(response)
        counter = 0
        async for response_txt in response_generator:
            if counter == 0:
                response_dict = {
                    "message": full_response,
                    "username": username,
                    "mode": "new",
                }
                await self.send({
                    "type": "websocket.send",
                    "text": json.dumps(response_dict),
                })
            if response_txt == r"%%%END%%%":
                counter += 1
                response_txt = "RAG has no answer to your question"
                encrypted_response_txt = encrypt_AES_ECB(response_txt, aes_key).decode('utf-8')
                full_response = full_response + response_txt
                response_dict = {
                    "message": encrypted_response_txt,
                    "username": username,
                    "mode": "continue",
                }
                await self.send({
                    "type": "websocket.send",
                    "text": json.dumps(response_dict),
                })
                break
            response_txt = response_txt.replace("", "")
            response_txt = response_txt.replace("<|im_end|>", "")
            encrypted_response_txt = encrypt_AES_ECB(response_txt, aes_key).decode('utf-8')
            full_response = full_response + response_txt
            response_dict = {
                "message": encrypted_response_txt,
                "username": username,
                "mode": "continue",
            }
            await self.send({
                "type": "websocket.send",
                "text": json.dumps(response_dict),
            })
            counter += 1
        message_id = await self.create_chat_message(full_response, rag_response=True, source_nodes=source_nodes_json)
        response_dict = {
            "message_id": message_id,
            "mode": "last",
        }
        await self.send({
            "type": "websocket.send",
            "text": json.dumps(response_dict),
        })

    async def websocket_disconnect(self, event):
        print("disconnected", event)

    # --- DB and utility methods ---
    @database_sync_to_async
    def get_thread(self, chat_id):
        return Thread.objects.get(id=chat_id)

    @database_sync_to_async
    def get_message(self, message_id):
        return ChatMessage.objects.get(id=message_id).message

    @database_sync_to_async
    def create_chat_message(self, message, rag_response, source_nodes):
        thread = self.thread
        user = self.scope["user"]
        msg = ChatMessage.objects.create(thread=thread, user=user, message=message, rag_response=rag_response, source_nodes=source_nodes)
        print("\nChat message saved\n")
        return msg.id

    @database_sync_to_async
    def get_doc_name(self, node_id):
        doc_id = node_id.split("_")[0]
        doc_name = Document.objects.get(id=doc_id).name
        return doc_name

    @database_sync_to_async
    def get_context(self, message_id):
        message_obj = ChatMessage.objects.get(id=message_id)
        contexts_json = message_obj.source_nodes
        return contexts_json

    async def query_engine_streamer(self, response):
        try:
            response_gen = response.response_gen
        except Exception:
            yield r"%%%END%%%"
            return
        try:
            while True:
                yield next(response_gen)
                await asyncio.sleep(0)
        except StopIteration:
            pass

    def translate_to_fa(self, text):
        return translate_en_fa(text)

    
    def keyword_extractor(self, text, model, tokenizer, keyword_extractor_prompt):
        # ----- User query -----
        user_query = text

        # ----- Final prompt -----
        prompt = f"{keyword_extractor_prompt}User: {user_query}\nKeywords:"

        # ----- Tokenize -----
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

        # ----- Generate -----
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=30,
                temperature=0.7,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id
            )

        # ----- Decode and print result -----
        generated_text = tokenizer.decode(output[0], skip_special_tokens=True)
        print("---- Raw Output ----")
        print(generated_text)

        # ----- Extract only the keyword list -----
        # This will remove the prompt and just keep the generated keywords
        extracted_keywords = generated_text.split("Keywords:")[-1].strip()
        print("\n---- Extracted Keywords ----")
        print(extracted_keywords)

        return extracted_keywords