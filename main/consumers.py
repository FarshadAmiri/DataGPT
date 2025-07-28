import asyncio
import json
from django.contrib.auth import get_user_model
from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async
import chromadb
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
from main.views import model, tokenizer, device
from main.models import Thread, ChatMessage, Document
from main.utilities.RAG import embedding_model, sentence_transformer_ef
from main.utilities.translation import translate_en_fa, translate_fa_en, detect_language
from main.utilities.variables import system_prompt, query_wrapper_prompt
from main.utilities.encryption import *
from main.utilities.helper_functions import remove_non_printable

class RAGConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        self.user = self.scope["user"]
        chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        self.thread = await self.get_thread(chat_id)

        try:
            db = chromadb.PersistentClient(path=self.thread.loc)
            chroma_collection = db.get_or_create_collection("default", embedding_function=sentence_transformer_ef)
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            llm = HuggingFaceLLM(
                context_window=4096,
                max_new_tokens=512,
                system_prompt=system_prompt,
                query_wrapper_prompt=SimpleInputPrompt("{query_str} [/INST]"),
                model=model,
                tokenizer=tokenizer
            )

            service_context = ServiceContext.from_defaults(
                chunk_size=1024,
                chunk_overlap=20,
                llm=llm,
                embed_model=embedding_model
            )
            set_global_service_context(service_context)

            self.index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)

        except Exception as e:
            print(f"RAG setup failed: {e}")
            self.index = None

        await self.send({"type": "websocket.accept"})

    async def websocket_receive(self, event):
        dict_data = json.loads(event.get("text", "{}"))
        if dict_data.get("mode") == "translation":
            await self.handle_translation(dict_data)
        elif dict_data.get("mode") == "context":
            await self.handle_context(dict_data)
        else:
            await self.handle_user_query(dict_data)

    async def handle_user_query(self, dict_data):
        username = self.user.username
        encrypted_message = dict_data.get("encrypted_message")
        encrypted_aes_key = dict_data.get("encrypted_aes_key")
        chat_mode = dict_data.get("chat_mode")
        cutoff = float(dict_data.get("similarity_cutoff", 0.3))

        aes_key = decrypt_aes_key(encrypted_aes_key)
        msg = decrypt_AES_ECB(encrypted_message, aes_key)
        msg = remove_non_printable(msg)
        await self.create_chat_message(msg, rag_response=False, source_nodes=None)

        full_response = ""

        if chat_mode == "standard":
            messages = [{"role": "user", "content": msg}]
            inputs = tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt"
            ).to(device)

            outputs = model.generate(
                **inputs,
                max_new_tokens=400,
                do_sample=True,
                temperature=0.7,
                top_p=0.9
            )

            full_response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
            encrypted_text = encrypt_AES_ECB(full_response, aes_key).decode('utf-8')
            await self.send({"type": "websocket.send", "text": json.dumps({
                "message": encrypted_text,
                "username": username,
                "mode": "new"
            })})
            message_id = await self.create_chat_message(full_response, rag_response=False, source_nodes=None)
            await self.send({"type": "websocket.send", "text": json.dumps({"message_id": message_id, "mode": "last"})})
            return

        if self.index is None:
            error_text = encrypt_AES_ECB("RAG is not available.", aes_key).decode('utf-8')
            await self.send({"type": "websocket.send", "text": json.dumps({"message": error_text, "username": username, "mode": "new"})})
            return

        retriever = VectorIndexRetriever(index=self.index, similarity_top_k=3)
        response_synth = get_response_synthesizer(streaming=False)

        query_engine = RetrieverQueryEngine(
            retriever=retriever,
            response_synthesizer=response_synth,
            node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=cutoff)]
        )

        response = query_engine.query(msg)
        source_nodes = response.source_nodes or []
        if len(source_nodes) == 0:
            full_response = "RAG could not find relevant content."
        else:
            full_response = response.response

        encrypted_text = encrypt_AES_ECB(full_response, aes_key).decode('utf-8')
        await self.send({"type": "websocket.send", "text": json.dumps({
            "message": encrypted_text,
            "username": username,
            "mode": "new"
        })})

        node_dict = {}
        for node in source_nodes:
            rels = node.node.relationships
            key = list(rels.keys())[0]
            doc_id = rels[key].node_id.split("_")[0]
            doc_name = await self.get_doc_name(doc_id)
            node_dict[doc_name] = node.text

        message_id = await self.create_chat_message(full_response, rag_response=True, source_nodes=json.dumps(node_dict))
        await self.send({"type": "websocket.send", "text": json.dumps({"message_id": message_id, "mode": "last"})})

    async def websocket_disconnect(self, event):
        print("WebSocket disconnected")

    async def handle_translation(self, dict_data):
        message_id = dict_data.get("message_id")
        encrypted_aes_key = dict_data.get("encrypted_aes_key")
        aes_key = decrypt_aes_key(encrypted_aes_key)
        translation_task = await self.get_message(message_id)
        translated = translate_en_fa(translation_task)
        encrypted_response = encrypt_AES_ECB(translated, aes_key).decode('utf-8')
        await self.send({"type": "websocket.send", "text": json.dumps({
            "encrypted_persian_translation": encrypted_response,
            "message_id": message_id,
            "mode": "translation"
        })})

    async def handle_context(self, dict_data):
        message_id = dict_data.get("message_id")
        encrypted_aes_key = dict_data.get("encrypted_aes_key")
        aes_key = decrypt_aes_key(encrypted_aes_key)
        contexts_json = await self.get_context(message_id)
        contexts = json.loads(contexts_json)
        encrypted_contexts = {
            encrypt_AES_ECB(k, aes_key).decode('utf-8'): encrypt_AES_ECB(v, aes_key).decode('utf-8')
            for k, v in contexts.items()
        }
        await self.send({"type": "websocket.send", "text": json.dumps({
            "mode": "context",
            "message_id": message_id,
            "encrypted_contexts": encrypted_contexts
        })})

    @database_sync_to_async
    def get_thread(self, chat_id):
        return Thread.objects.get(id=chat_id)

    @database_sync_to_async
    def get_message(self, message_id):
        return ChatMessage.objects.get(id=message_id).message

    @database_sync_to_async
    def create_chat_message(self, message, rag_response, source_nodes):
        return ChatMessage.objects.create(
            thread=self.thread,
            user=self.scope["user"],
            message=message,
            rag_response=rag_response,
            source_nodes=source_nodes
        ).id

    @database_sync_to_async
    def get_doc_name(self, doc_id):
        return Document.objects.get(id=doc_id).name

    @database_sync_to_async
    def get_context(self, message_id):
        return ChatMessage.objects.get(id=message_id).source_nodes
