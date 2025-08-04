import asyncio, json
from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async
import chromadb
from llama_index.vector_stores import ChromaVectorStore
from llama_index.storage.storage_context import StorageContext
from llama_index.llms import HuggingFaceLLM
from llama_index.retrievers import VectorIndexRetriever
from llama_index.postprocessor import SimilarityPostprocessor
from llama_index.query_engine import RetrieverQueryEngine
from llama_index import VectorStoreIndex, ServiceContext, set_global_service_context, get_response_synthesizer
from transformers import TextStreamer, TextIteratorStreamer
from main.utilities.encryption import decrypt_AES_ECB, decrypt_aes_key, encrypt_AES_ECB
from main.utilities.helper_functions import remove_non_printable
from main.models import Thread, ChatMessage, Document
from main.utilities.RAG import embedding_model_st, embedding_model_st2
from main.utilities.variables import system_prompt
from main.views import model, tokenizer, device

class RAGConsumer(AsyncConsumer):

    async def websocket_connect(self, event):
        self.user = self.scope["user"]
        chat_id = self.scope["url_route"]["kwargs"].get("chat_id")
        try:
            self.thread = await self.get_thread(chat_id)
            db = chromadb.PersistentClient(path=self.thread.loc)
            coll = db.get_or_create_collection("default", embedding_function=embedding_model_st2)
            vs = ChromaVectorStore(chroma_collection=coll)
            storage = StorageContext.from_defaults(vector_store=vs)
            set_global_service_context(ServiceContext.from_defaults(
                chunk_size=1024, chunk_overlap=20,
                llm=HuggingFaceLLM(
                    context_window=4096, max_new_tokens=512,
                    system_prompt=system_prompt,
                    query_wrapper_prompt=None,
                    model=model, tokenizer=tokenizer
                ), embed_model=embedding_model_st
            ))
            self.index = VectorStoreIndex.from_vector_store(vs, storage)
        except Exception as e:
            print("Init error:", e)
            self.index = None

        await self.send({"type": "websocket.accept"})

    async def websocket_receive(self, event):
        data = json.loads(event.get("text", "{}"))
        required = ("encrypted_message", "encrypted_aes_key", "chat_mode")
        if not all(k in data for k in required):
            await self.send_error("Missing required fields")
            return

        chat_mode = data["chat_mode"]
        cutoff = float(data.get("similarity_cutoff", 0.3))
        enc_msg = data["encrypted_message"]
        enc_key = data["encrypted_aes_key"]

        aes_key = decrypt_aes_key(enc_key)
        try:
            msg = remove_non_printable(decrypt_AES_ECB(enc_msg, aes_key))
        except Exception:
            await self.send_error("Invalid encrypted_message")
            return

        await self.create_chat_message(msg, rag_response=False, source_nodes=None)
        username = self.user.username

        if chat_mode == "standard":
            await self.handle_standard(msg, username, aes_key)
        else:
            await self.handle_rag(msg, username, aes_key, cutoff)


    async def handle_standard(self, msg, username, aes_key):
        messages = [{"role": "user", "content": msg}]
        inputs = tokenizer.apply_chat_template(messages, add_generation_prompt=True,
                                               tokenize=True, return_dict=True,
                                               return_tensors="pt").to(device)

        queue = asyncio.Queue()
        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

        def gen():
            model.generate(**inputs, max_new_tokens=400, do_sample=True,
                           temperature=0.7, top_p=0.95,
                           pad_token_id=tokenizer.eos_token_id,
                           streamer=streamer)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, gen)

        # drain sync streamer
        for token in streamer:
            queue.put_nowait(token)

        full = ""
        first = True
        while not queue.empty():
            token = await queue.get()
            full += token
            encrypted = encrypt_AES_ECB(token, aes_key).decode('utf-8')
            await self.send({"type":"websocket.send", "text":json.dumps({
                "message": encrypted,
                "username": username,
                "mode": "new" if first else "continue"
            })})
            first = False

        msg_id = await self.create_chat_message(full, rag_response=False, source_nodes=None)
        await self.send({"type":"websocket.send","text":json.dumps({"message_id": msg_id,"mode": "last"})})


    async def handle_rag(self, msg, username, aes_key, cutoff):
        if not self.index:
            await self.send_message("RAG not available", username, aes_key, final=True)
            return

        retr = VectorIndexRetriever(index=self.index, similarity_top_k=3)
        qe = RetrieverQueryEngine(retriever=retr, response_synthesizer=get_response_synthesizer(streaming=True),
                                  node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=cutoff)])
        response = qe.query(msg)
        source_nodes = response.source_nodes or []

        if not source_nodes:
            await self.send_message("RAG has no answer to your question", username, aes_key, final=True)
            return

        first = True; full = ""
        async for token in self.query_engine_streamer(response):
            clean = token.replace("</s>", "").replace("<|im_end|>", "")
            full += clean
            encrypted = encrypt_AES_ECB(clean, aes_key).decode('utf-8')
            await self.send({"type":"websocket.send","text":json.dumps({
                "message": encrypted,
                "username": username,
                "mode": "new" if first else "continue"
            })})
            first = False

        source_dict = {}
        for node in source_nodes:
            node_id = list(node.node.relationships.values())[0].node_id
            doc_name = await self.get_doc_name(node_id)
            source_dict[doc_name] = node.text

        msg_id = await self.create_chat_message(full, rag_response=True, source_nodes=json.dumps(source_dict))
        await self.send({"type":"websocket.send","text":json.dumps({"message_id": msg_id,"mode": "last"})})


    async def send_message(self, text, username, aes_key, final=False):
        encrypted = encrypt_AES_ECB(text, aes_key).decode('utf-8')
        await self.send({"type":"websocket.send","text":json.dumps({
            "message": encrypted,
            "username": username,
            "mode": "new" if not final else "last"
        })})

    async def send_error(self, msg):
        await self.send({"type":"websocket.send","text":json.dumps({"error": msg})})

    @database_sync_to_async
    def create_chat_message(self, message, rag_response, source_nodes):
        return ChatMessage.objects.create(
            thread=self.thread, user=self.user,
            message=message, rag_response=rag_response,
            source_nodes=source_nodes
        ).id

    @database_sync_to_async
    def get_doc_name(self, node_id):
        doc_id = node_id.split("_")[0]
        return Document.objects.get(id=doc_id).name

    async def query_engine_streamer(self, response):
        try:
            gen = response.response_gen
        except Exception:
            yield "%%%END%%%"; return
        while True:
            try:
                yield next(gen)
                await asyncio.sleep(0)
            except StopIteration:
                break

    @database_sync_to_async
    def get_thread(self, chat_id):
        return Thread.objects.get(id=chat_id)

    async def websocket_disconnect(self, event):
        # Optional cleanup logic if needed
        print("WebSocket disconnected.")