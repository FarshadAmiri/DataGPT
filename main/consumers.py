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
from main.models import Thread, ChatMessage, Document
from main.utilities.RAG import llm_inference
from main.utilities.translation import translate_en_fa, translate_fa_en, detect_language
from main.utilities.variables import system_prompt, query_wrapper_prompt


class RAGConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        print("connected", event)
        self.user = self.scope["user"]
        try:
            chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
            thread = await self.get_thread(chat_id=chat_id)
            self.thread = thread
            print(f"\nthread.loc: {thread.loc}\n")
            db = chromadb.PersistentClient(path=thread.loc)
            chroma_collection = db.get_or_create_collection("default")
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
        except:
            pass
        # Create a system prompt
        # system_prompt = """<s>[INST] <<SYS>>
        # You are a helpful, respectful and honest assistant. Always answer as
        # helpfully as possible, while being safe.`
        # If a question does not make any sense, or is not factually coherent, explain
        # why instead of answering something not correct. If you don't know the answer
        # to a question, please don't share false information.
        # Try to be exact in information and numbers you tell.
        # Your goal is to provide answers completely based on the information provided
        # and avoid to use yourown knowledge.<</SYS>>
        # """
        # query_wrapper_prompt = SimpleInputPrompt("{query_str} [/INST]")
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
        try: 
            index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
            # query_engine = index.as_query_engine()

            # Customize query engine
            retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=6,
            )

            retriever_10 = VectorIndexRetriever(
                index=index,
                similarity_top_k=3,
            )
            
            retriever_00 = VectorIndexRetriever(
                index=index,
                similarity_top_k=1,
            )

            # configure response synthesizer
            response_synthesizer = get_response_synthesizer(streaming=True)

            # assemble query engine
            query_engine = RetrieverQueryEngine(
                retriever=retriever,
                response_synthesizer=response_synthesizer,
                node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.3)],
            )

            query_engine_10 = RetrieverQueryEngine(
                retriever=retriever_10,
                response_synthesizer=response_synthesizer,
                node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.10)],
            )

            query_engine_00 = RetrieverQueryEngine(
                retriever=retriever_00,
                response_synthesizer=response_synthesizer,
                node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.0)],
            )
            
            self.query_engine = query_engine
            self.query_engine_10 = query_engine_10
            self.query_engine_00 = query_engine_00
        except:
            pass


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

    # async def websocket_receive(self, event):
    #     print("receive", event)
    #     client_data = event.get('text', None)
    #     if client_data is not None:
    #         dict_data = json.loads(client_data)
    #         msg = dict_data.get("message")
    #         username = self.user.username
    #         await self.create_chat_message(msg, rag_response=False)
    #         print(f"msg: {msg}")
    #         response = self.query_engine.query(msg)
    #         print(f"\n\nresponse: {response}\n\n")
    #         await self.create_chat_message(response, rag_response=True)
            
    #         response_dict = {
    #             # "message": response.response,
    #             "message": response.response,
    #             "username": username,
    #         }

    #         await self.send(
    #             {
    #             "type": "websocket.send",
    #             "text": json.dumps(response_dict),
    #             }
    #         )


    async def websocket_receive(self, event):
        print("receive", event)
        client_data = event.get('text', None)
        if client_data is not None:
            dict_data = json.loads(client_data)
            mode = dict_data.get("mode")
            msg = dict_data.get("message")
            if mode == "translation":
                translation_task = dict_data.get("translate_to_fa")
                message_id = dict_data.get("message_id")
                persian_translation = self.translate_to_fa(translation_task)
                response_dict = {
                    "persian_translation": persian_translation,
                    "message_id": message_id,
                    "mode": "translation",
                }
                await self.send({
                    "type": "websocket.send",
                    "text": json.dumps(response_dict),
                })

            elif mode == "context":
                message_id = dict_data.get("message_id")
                contexts = await self.get_context(message_id)
                contexts = json.loads(contexts)

                response_dict = {
                    "mode": "context",
                    "message_id": message_id,
                    "contexts": contexts,
                }
                await self.send({
                    "type": "websocket.send",
                    "text": json.dumps(response_dict),
                })

            else:
                username = self.user.username
                print(f"msg: {msg}")
                await self.create_chat_message(msg, rag_response=False, source_nodes=None)
                response_dict = {
                    "message": "",
                    "username": username,
                    "mode": "new",
                }
                await self.send({
                    "type": "websocket.send",
                    "text": json.dumps(response_dict),
                })

                # Translate the question if it is Persian
                if detect_language(msg) == "Persian":
                    msg = translate_fa_en(msg)
                
                full_response = ""
                # response_generator = self.query_engine_streamer(msg)
                ########
                response = self.query_engine.query(msg)
                if len(response.source_nodes) == 0 :
                    response = self.query_engine_10.query(msg)
                    if len(response.source_nodes) == 0 :
                        response = self.query_engine_00.query(msg)
                        full_response = "No relevant information was found in the document sources; here is the LLM response generated to address your question:\n"
                source_nodes = response.source_nodes
                source_nodes_dict = dict()
                for node in source_nodes:
                    metadata = node.node.relationships
                    key = list(metadata.keys())[0]
                    node_id = metadata[key].node_id
                    doc_name = await self.get_doc_name(node_id)
                    node_text = node.text
                    source_nodes_dict[doc_name] = node_text
                source_nodes_json = json.dumps(source_nodes_dict)
                response_generator = self.query_engine_streamer(response)
                #############
                async for response_txt in response_generator:
                    response_txt = response_txt.replace("</s>", "")
                    response_txt = response_txt.replace("<|im_end|>", "")
                    full_response = full_response + response_txt
                    response_dict = {
                        "message": response_txt,
                        "username": username,
                        "mode": "continue",
                    }
                    await self.send({
                        "type": "websocket.send",
                        "text": json.dumps(response_dict),
                    })
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

    @database_sync_to_async
    def get_thread(self, chat_id):
        return Thread.objects.get(id=chat_id)
    
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
        # contexts_dict = json.loads(contexts_json)
        return contexts_json
    

    async def query_engine_streamer(self, response):
        response_gen = response.response_gen
        try:
            while True:
                yield next(response_gen)
                await asyncio.sleep(0)
        except StopIteration:
            pass

    def translate_to_fa(self, text):
        persian_translation = translate_en_fa(text)
        return persian_translation