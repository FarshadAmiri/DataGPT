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
from llama_index import VectorStoreIndex, ServiceContext, set_global_service_context,  get_response_synthesizer
from llama_index.retrievers import VectorIndexRetriever
from llama_index.query_engine import RetrieverQueryEngine
from llama_index.postprocessor import SimilarityPostprocessor
from main.views import model, tokenizer, streamer, device
from main.models import Thread, ChatMessage
from main.utilities.RAG import llm_inference


class RAGConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        print("connected", event)
        self.user = self.scope["user"]
        chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        thread = await self.get_thread(chat_id=chat_id)
        self.thread = thread
        print(f"\nthread.loc: {thread.loc}\n")
        db = chromadb.PersistentClient(path=thread.loc)
        chroma_collection = db.get_or_create_collection("default")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        # Create a system prompt
        system_prompt = """<s>[INST] <<SYS>>
        You are a helpful, respectful and honest assistant. Always answer as
        helpfully as possible, while being safe.`
        If a question does not make any sense, or is not factually coherent, explain
        why instead of answering something not correct. If you don't know the answer
        to a question, please don't share false information.
        Try to be exact in information and numbers you tell.
        Your goal is to provide answers based on the information provided and your other knowledge.<</SYS>>
        """
        query_wrapper_prompt = SimpleInputPrompt("{query_str} [/INST]")
        llm = HuggingFaceLLM(context_window=4096,
                     max_new_tokens=512,
                     system_prompt=system_prompt,
                     query_wrapper_prompt=query_wrapper_prompt,
                     model=model,
                     tokenizer=tokenizer)

        embeddings = LangchainEmbedding(    
        HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")        
        )
        # Create new service context instance
        service_context = ServiceContext.from_defaults(
            chunk_size=1024,
            chunk_overlap=20,
            llm=llm,
            embed_model=embeddings
        )
        # And set the service context
        set_global_service_context(service_context)
        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
        query_engine = index.as_query_engine()
        # retriever = VectorIndexRetriever(
        #     index=index,
        #     similarity_top_k=3,
        #     doc_id = ["fe0ab12b-146f-45e2-9161-387ac90f8031"]
        # )

        # # configure response synthesizer
        # response_synthesizer = get_response_synthesizer(streaming=True)

        # # assemble query engine
        # query_engine = RetrieverQueryEngine(
        #     retriever=retriever,
        #     response_synthesizer=response_synthesizer,
        #     node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.2)],
        # )
        self.query_engine = query_engine
        response = query_engine.query("what is machine? explain in less than 100 words")
        print(f"\nresponse.response: {response.response}\n")

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
        self.send({
            "type": "websocket.accept"
        })

    async def websocket_receive(self, event):
        print("receive", event)
        client_data = event.get('text', None)
        if client_data is not None:
            dict_data = json.loads(client_data)
            msg = dict_data.get("message")
            username = self.user.username
            await self.create_chat_message(msg, rag_response=False)
            print(f"msg: {msg}")
            response = self.query_engine.query(msg)
            response = llm_inference(msg, model, tokenizer, device)
            print(f"\n\nresponse: {response}\n\n")
            await self.create_chat_message(response, rag_response=True)
            
            response_dict = {
                # "message": response.response,
                "message": response,
                "username": username,
            }

            await self.send(
                {
                "type": "websocket.send",
                "text": json.dumps(response_dict),
                }
            )


    async def websocket_disconnect(self, event):
        print("disconnected", event)

    @database_sync_to_async
    def get_thread(self, chat_id):
        return Thread.objects.get(id=chat_id)
    
    @database_sync_to_async
    def create_chat_message(self, message, rag_response: bool):
        thread = self.thread
        user = self.scope["user"]
        ChatMessage.objects.create(thread=thread, user=user, message=message, rag_response=rag_response)
        print("\nChat message saved\n")
        return