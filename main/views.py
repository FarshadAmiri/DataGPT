from django.shortcuts import render, redirect
from main.utilities.RAG import load_model, llm_inference
from main.models import Thread, Document, ChatMessage, Collection
from django.contrib.auth.decorators import login_required, permission_required
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import Max, Count
from main.utilities.helper_functions import create_folder, get_first_words
from main.utilities.RAG import create_rag, add_docs, index_builder
from pathlib import Path
import os, shutil
from llama_index import SimpleDirectoryReader

vector_db_path = "vector_dbs"

model_obj = load_model()
model = model_obj["model"]
tokenizer = model_obj["tokenizer"]
device = model_obj["device"]
streamer = model_obj["streamer"]


@login_required(login_url='users:login')
def chat_view(request, thread_id=None):
    print(f"\nchat_id: {thread_id}\n")
    user = request.user
    if request.method == "GET":
        threads = Thread.objects.filter(user=user).annotate(last_message_timestamp=Max('chatmessage__timestamp'))
        threads = threads.order_by('-last_message_timestamp')
        if (thread_id is None) and (len(threads) > 0):
            thread_id = int(threads[0].id)
            return redirect('main:chat', thread_id=thread_id)
        elif len(threads) == 0:
            context = {"no_threads": True, "active_thread_id": 0,}
            return render(request, 'main/chat.html', context)
        threads_preview = dict()
        for thread in threads:
            if ChatMessage.objects.filter(thread__id=thread.id).count() > 0:
                txt = ChatMessage.objects.filter(thread__id=thread.id).latest('timestamp').message[:80]
                msg_initial_words = get_first_words(txt, 60) + "..."
                threads_preview[thread.id] = msg_initial_words
            else:
                threads_preview[thread.id] = "Empty chat"

        print(f"\nthreads_preview: {threads_preview}\n")
        print(f"\nthread_id: {thread_id}\n")
        print(f"\nactive_thread_id: {type(thread_id)} {thread_id}\n")
        # Delete threads directories that their model instance have been removed before.
        try:
            threads_names = ["vdb_" + x for x in list(threads.values_list("name", flat=True))]
            user_db_path = os.path.join(vector_db_path, user.username)
            user_db_vdbs = os.listdir(user_db_path)
            to_be_deleted_threads = [vdb for vdb in user_db_vdbs if vdb not in threads_names]
            for vdb in to_be_deleted_threads:
                try:
                    vdb_path = os.path.join(user_db_path, vdb)
                    shutil.rmtree(vdb_path, ignore_errors=False, onerror=None)
                except:
                    continue
        except:
            pass
        thread_id = int(thread_id)
        messages = ChatMessage.objects.filter(user=user, thread=thread_id)
        active_thread = Thread.objects.get(id=thread_id)
        active_thread_name = thread.name
        rag_docs = active_thread.docs.all()
        context = {"chat_threads": threads, "active_thread_id": thread_id, "active_thread_name": active_thread_name,"rag_docs": rag_docs,
                    "messages": messages, "threads_preview": threads_preview}
        return render(request, 'main/chat.html', context)


@login_required(login_url='users:login')
def create_rag_view(request,):  # Erros front should handle: 1-similar rag_name, 2-avoid creating off limit rag, 3- error when rag_name is not given
    user = request.user
    if request.method == "POST":
        global model, tokenizer, vector_db_path
        uploaded_files = request.FILES.getlist('files')
        rag_name = request.POST.get("new-rag-name", None)
        vdb_path = os.path.join(vector_db_path, user.username, f'vdb_{rag_name}')
        docs_path = os.path.join(vdb_path, "docs")
        create_rag(vdb_path)
        create_folder(docs_path)

        # docs = []
        # docs_paths = []
        # docs_dict = dict()

        rag_parameters = index_builder(vdb_path, model, tokenizer)
        index, loader = rag_parameters["index"], rag_parameters["loader"]
        vdb = Thread.objects.create(user=user, name=rag_name, public=False, 
                                    description=None, loc=vdb_path)
        for file in uploaded_files:
            file_name = file.name
            print(f"\nfile_name: {file_name} is in progress...\n")
            doc_path = os.path.join(docs_path, file_name)
            doc_path = default_storage.get_available_name(doc_path)
            default_storage.save(doc_path, ContentFile(file.read()))

            # document = loader.load(file_path=Path(doc_path), metadata=False)
            document = SimpleDirectoryReader(input_files=[doc_path]).load_data()

            # Create indexes
            for chunked_doc in document:
                index.insert(chunked_doc)
            doc_obj = Document.objects.create(user=user, name=file_name, public=False,
                                              description=None, loc=doc_path)
            vdb.docs.add(doc_obj)

            # docs.append(doc_obj)
            # docs_paths.append(doc_path)

            # docs_dict[file_name] = dict()
            # docs_dict[file_name]["user"] = user
            # docs_dict[file_name]["public"] = False
            # docs_dict[file_name]["description"] = None
            # docs_dict[file_name]["loc"] = doc_path
            # docs_dict[file_name]["doc_obj"] = doc_obj
        
        # vdb.docs.set(docs)
        # add_docs(vdb_path, docs_paths)

        return redirect('main:chat', thread_id=vdb.id)


@login_required(login_url='users:login')    
def collections_view(request,  collection_id=None,):
    user = request.user
    if request.method == "GET":
        collections = Collection.objects.annotate(total_docs=Count('docs')).values('name', 'total_docs')
        if (collection_id is None) and (len(collections) > 0):
            collection_id = int(collections[0].id)
            return redirect('main:chat', collection_id=collection_id)
        elif len(collections) == 0:
            context = {"no_collections": True, "active_collection_id": 0,}
            return render(request, 'main/collections.html', context)
        
        collection_id = int(collection_id)
        collection = Collection.objects.get(id=collection_id)
        documents = collection.docs.all()
        context = {"collections": collections, "active_collection_id": collection.id, "active_collection_name": collection.name,
                    "documents": documents,}
        render(request, 'main/collections.html', context)


@login_required(login_url='users:login')    
def create_collection_view(request,):
    user = request.user
    if request.method == "GET":
        return
        collections = Collection.objects.all()
        context = {"collections": collections, "user": user, }
        render(request, 'main/collections.html', context)


@login_required(login_url='users:login')    
def delete_collection(request, collection_id):
    user = request.user
    collection_id = int(collection_id)
    collection = Collection.objects.get(user=user, id=collection_id)
    collection.delete()
    return redirect('main:main_collections')


@login_required(login_url='users:login')
def add_docs_view(request, thread_id):
    user = request.user
    if request.method == "POST":
        global vector_db_path, model, tokenizer
        uploaded_files = request.FILES.getlist('files')
        thread_id = int(thread_id)
        thread = Thread.objects.get(user=user, id=thread_id)
        rag_name = thread.name
        vdb_path = os.path.join(vector_db_path, user.username, f'vdb_{rag_name}')
        docs_path = os.path.join(vdb_path, "docs")
        rag_parameters = index_builder(vdb_path, model, tokenizer)
        index, loader = rag_parameters["index"], rag_parameters["loader"]
        vdb = Thread.objects.get(user=user, name=rag_name,)
        for file in uploaded_files:
            file_name = file.name
            print(f"\nfile_name: {file_name} is in progress...\n")
            doc_path = os.path.join(docs_path, file_name)
            doc_path = default_storage.get_available_name(doc_path)
            default_storage.save(doc_path, ContentFile(file.read()))

            # document = loader.load(file_path=Path(doc_path), metadata=False)
            document = SimpleDirectoryReader(input_files=[doc_path]).load_data()

            # Create indexes
            for chunked_doc in document:
                index.insert(chunked_doc)
            doc_obj = Document.objects.create(user=user, name=file_name, public=False,
                                              description=None, loc=doc_path)
            vdb.docs.add(doc_obj)
        return redirect('main:chat', thread_id=thread_id)


@login_required(login_url='users:login')
def delete_thread(request, thread_id):
    user = request.user
    thread_id = int(thread_id)
    thread = Thread.objects.get(user=user, id=thread_id)
    thread.delete()
    return redirect('main:main_chat')