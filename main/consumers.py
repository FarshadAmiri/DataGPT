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
from main.utilities.RAG import embedding_model, sentence_transformer_ef
from main.utilities.translation import translate_en_fa, translate_fa_en, detect_language
from main.utilities.variables import system_prompt, query_wrapper_prompt
from main.utilities.encryption import *
from main.utilities.helper_functions import remove_non_printable


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
            chroma_collection = db.get_or_create_collection("default", embedding_function=sentence_transformer_ef)
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

        # Create new service context instance
        service_context = ServiceContext.from_defaults(
            chunk_size=1024,
            chunk_overlap=20,
            llm=llm,
            embed_model=embedding_model
        )
        # And set the service context
        set_global_service_context(service_context)
        try: 
            index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
            # query_engine = index.as_query_engine()

            # Customize query engine
            retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=3,
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
                node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.35)],
            )

            query_engine_10 = RetrieverQueryEngine(
                retriever=retriever_10,
                response_synthesizer=response_synthesizer,
                node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.2)],
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
        client_data = event.get('text', None)
        if client_data is not None:
            dict_data = json.loads(client_data)
            mode = dict_data.get("mode")
            if mode == "translation":
                message_id = dict_data.get("message_id")
                translation_task = await self.get_message(message_id)
                # encrypted_translation_task = dict_data.get("encrypted_message")
                encrypted_aes_key = dict_data.get("encrypted_aes_key")
                aes_key = decrypt_aes_key(encrypted_aes_key)
                # translation_task = decrypt_AES_ECB(encrypted_translation_task, aes_key)
                # translation_task = translation_task.replace("\x02", "")
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

            elif mode == "context":
                message_id = dict_data.get("message_id")
                contexts = await self.get_context(message_id)
                encrypted_aes_key = dict_data.get("encrypted_aes_key")
                aes_key = decrypt_aes_key(encrypted_aes_key)
                contexts = json.loads(contexts)
                encrypted_contexts = dict()
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

            else:
                username = self.user.username
                encrypted_message = dict_data.get("encrypted_message")
                encrypted_aes_key = dict_data.get("encrypted_aes_key")
                aes_key = decrypt_aes_key(encrypted_aes_key)
                msg = decrypt_AES_ECB(encrypted_message, aes_key)
                msg = remove_non_printable(msg)
                print(f"msg: {msg}")
                await self.create_chat_message(msg, rag_response=False, source_nodes=None)

                # Translate the question if it is Persian
                if detect_language(msg) == "Persian":
                    msg = translate_fa_en(msg)
                    if msg.strip() == "":
                        msg = "Empty message"
                print("msg: ", msg)
                full_response = ""
                # response_generator = self.query_engine_streamer(msg)
                ########
                response = self.query_engine.query(msg)
                if len(response.source_nodes) == 0 :
                    response = self.query_engine_10.query(msg)
                    if len(response.source_nodes) == 0 :
                        response = self.query_engine_00.query(msg)
                        full_response = "No relevant information was found in the document sources; here is the LLM response generated to address your question:\n"

                # response_dict = {
                #     "message": full_response,
                #     "username": username,
                #     "mode": "new",
                # }
                # await self.send({
                #     "type": "websocket.send",
                #     "text": json.dumps(response_dict),
                # })

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
                    response_txt = response_txt.replace("</s>", "")
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
        # contexts_dict = json.loads(contexts_json)
        return contexts_json
    

    async def query_engine_streamer(self, response):
        try:
            response_gen = response.response_gen
        except:
            yield r"%%%END%%%"
            return
        try:
            while True:
                yield next(response_gen)
                await asyncio.sleep(0)
        except StopIteration:
            pass

    def translate_to_fa(self, text):
        persian_translation = translate_en_fa(text)
        return persian_translation