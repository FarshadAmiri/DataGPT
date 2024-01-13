from django.shortcuts import render, redirect
from main.utilities.RAG import load_model, llm_inference
from main.models import Thread, Document
from django.contrib.auth.decorators import login_required, permission_required
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from main.utilities.helper_functions import create_folder
from main.utilities.RAG import create_rag
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
        if chat_id is None:
            chat_threads = Thread.objects.filter(user=user)
            chat_id = chat_threads[0].id
            return redirect('main:chat', chat_id=chat_id)
        chat_threads = Thread.objects.filter(user=user)
        print(f"\nchat_id: {chat_id}\n")
        print(f"\nactive_thread_id: {type(chat_id)} {chat_id}\n")
        context = {"chat_threads": chat_threads,
                   "active_thread_id": int(chat_id)
                   }
        return render(request, 'main/chat.html', context)


@login_required(login_url='users:login')
def create_rag_view(request,):   # Erros front should handle: 1-similar rag_name, 2-avoid creating off limit rag, 3- error when rag_name is not given
    user = request.user
    if request.method == "POST":
        uploaded_files = request.FILES.getlist('files')
        rag_name = request.POST.get("new-rag-name", None)
        vdb_path = os.path.join(vector_db_path, user.username, f'vdb_{rag_name}')
        docs_path = os.path.join(vdb_path, "docs")
        create_rag(vdb_path)
        create_folder(docs_path)
        docs = []

        for file in uploaded_files:
            file_name = file.name
            doc_path = os.path.join(docs_path, file_name)
            default_storage.save(doc_path, ContentFile(file.read()))

            doc = Document.objects.create(user=user, name=file_name, public=False,
                                          description=None, loc=doc_path)
            docs.append(doc)
        
        vdb = Thread.objects.create(user=user, name=rag_name, public=False, 
                                       description=None, loc=vdb_path)
        vdb.docs.set(docs)

        return redirect('main:main_chat')