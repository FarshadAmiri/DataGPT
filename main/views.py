from django.shortcuts import render, redirect
from main.utilities.RAG import load_model, llm_inference
from main.models import Thread, Document, ChatMessage
from django.contrib.auth.decorators import login_required, permission_required
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from main.utilities.helper_functions import create_folder, get_first_words
from main.utilities.RAG import create_rag, add_docs, index_builder
from pathlib import Path
import os

vector_db_path = "vector_dbs"

model_obj = load_model()
model = model_obj["model"]
tokenizer = model_obj["tokenizer"]
device = model_obj["device"]
streamer = model_obj["streamer"]


@login_required(login_url='users:login')
def chat_view(request, chat_id=None):
    print(f"\nchat_id: {chat_id}\n")
    user = request.user
    if request.method == "GET":
        chat_threads = Thread.objects.filter(user=user)
        if (chat_id is None) and (len(chat_threads) > 0):
            chat_id = chat_threads[0].id
            return redirect('main:chat', chat_id=chat_id)
        threads_preview = dict()
        for thread in chat_threads:
            if ChatMessage.objects.filter(thread__id=thread.id).count() > 0:
                txt = ChatMessage.objects.filter(thread__id=thread.id).latest('timestamp').message[:80]
                msg_initial_words = get_first_words(txt, 60) + "..."
                threads_preview[thread.id] = msg_initial_words
            else:
                threads_preview[thread.id] = "Empty chat"

        print(f"\nthreads_preview: {threads_preview}\n")
        print(f"\nchat_id: {chat_id}\n")
        print(f"\nactive_thread_id: {type(chat_id)} {chat_id}\n")
        chat_id = int(chat_id)
        messages = ChatMessage.objects.filter(user=user, thread=chat_id)
        thread = Thread.objects.get(id=chat_id)
        rag_docs = thread.docs.all()
        context = {"chat_threads": chat_threads, "active_thread_id": chat_id, "rag_docs": rag_docs,
                   "messages": messages, "threads_preview": threads_preview}
        return render(request, 'main/chat.html', context)


@login_required(login_url='users:login')
def create_rag_view(request,):  # Erros front should handle: 1-similar rag_name, 2-avoid creating off limit rag, 3- error when rag_name is not given
    user = request.user
    if request.method == "POST":
        global model, tokenizer
        uploaded_files = request.FILES.getlist('files')
        rag_name = request.POST.get("new-rag-name", None)
        vdb_path = os.path.join(vector_db_path, user.username, f'vdb_{rag_name}')
        docs_path = os.path.join(vdb_path, "docs")
        create_rag(vdb_path)
        create_folder(docs_path)
        docs = []
        docs_paths = []

        docs_dict = dict()
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

            document = loader.load(file_path=Path(doc_path), metadata=False)

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

        return redirect('main:main_chat')
    

def testView(request,):
    return render(request, "main/test.html")