from django.shortcuts import render, redirect
# from main.utilities.RAG import load_model, llm_inference
from main.models import Thread, Document, ChatMessage, Collection
from users.models import User
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db.models import Max, Count
from main.utilities.helper_functions import create_folder, get_first_words, copy_folder_contents, hash_file
from main.utilities.RAG import create_rag, index_builder, create_all_docs_collection
from pathlib import Path
import os, shutil, random, string
from llama_index.core import SimpleDirectoryReader
from llama_index.core import SummaryIndex, Document as llama_index_doc
from main.utilities.encryption import *


vector_db_path = "vector_dbs"
collections_path = "collections"
all_docs_collection_name = "ALL_DOCS_COLLECTION"
all_docs_collection_path = os.path.join(collections_path, all_docs_collection_name)

# model_name = "TheBloke/Mistral-7B-Instruct-v0.2-AWQ"
# model_name = "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ"
# model_name = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"
# model_name = "TechxGenus/Meta-Llama-3-8B-Instruct-AWQ" 
# model_name = "TheBloke/CapybaraHermes-2.5-Mistral-7B-AWQ"
# model_name = "TheBloke/Llama-2-7b-Chat-GPTQ"
# model_name = "meta-llama/Meta-Llama-3-8B-Instruct"
# model_name = "solidrust/dolphin-2.9-llama3-8b-AWQ"
# model_name = "Farshad-Llama-3-8B-Instruct-AWQ"


# model_obj = load_model(model_name)
# model = model_obj["model"]
# tokenizer = model_obj["tokenizer"]
# device = model_obj["device"]
# streamer = model_obj["streamer"]


@login_required(login_url='users:login') 
def chat_view(request, thread_id=None):
    # print(f"\nchat_id: {thread_id}\n")
    user = request.user
    if request.method in ["POST" , "GET"]:
        if request.method == "POST":
            encrypted_aes_key = request.POST.get("encrypted_aes_key", None)
            aes_key = decrypt_aes_key(encrypted_aes_key)
        threads = Thread.objects.filter(user=user).annotate(last_message_timestamp=Max('chatmessage__timestamp'))
        threads = threads.order_by('-last_message_timestamp')
        if len(threads) == 0:
            # Check whether All docs collection exists in Collection table and filesystem
            create_all_docs_collection()
            collections = Collection.objects.exclude(name=all_docs_collection_name).values('id', 'name')
            context = {"no_threads": True, "active_thread_id": 0, 'collections': collections,}
            return render(request, 'main/chat.html', context)
        threads_preview = dict()
        for thread in threads:
            if ChatMessage.objects.filter(thread__id=thread.id).count() > 0:
                txt = ChatMessage.objects.filter(thread__id=thread.id).latest('timestamp').message[:80]
                preview_raw = get_first_words(txt, 40)
                preview_clean = ''.join(ch if (ch.isalnum() or ch.isspace() or ch in '.,!?') else '' for ch in preview_raw)
                preview_clean = ' '.join(preview_clean.split())  # collapse extra spaces
                msg_initial_words = (preview_clean + '...') if preview_clean else '...'
                threads_preview[thread.id] = msg_initial_words
            else:
                threads_preview[thread.id] = "Empty chat"

        # print(f"\nthreads_preview: {threads_preview}\n")
        # print(f"\nthread_id: {thread_id}\n")
        # print(f"\nactive_thread_id: {type(thread_id)} {thread_id}\n")
        threads_ids = [type(th.id) for th in threads]
        # print(f"\nthreads: {threads}\n")
        # print(f"\nthreads_ids: {threads_ids}\n")

        # Check whether All docs collection exists in Collection table and filesystem
        create_all_docs_collection()

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

        collections = Collection.objects.exclude(name=all_docs_collection_name).values('id', 'name')
        if (thread_id is None):
            # return redirect('main:chat', thread_id=thread_id)
            context = {"chat_threads": threads, "threads_preview": threads_preview, 'collections': collections, "no_active_thread": True,
                       "no_threads": True, "active_thread_id": 0,}
            return render(request, 'main/chat.html', context)
        thread_id = int(thread_id)
        messages = ChatMessage.objects.filter(user=user, thread=thread_id)
        for message in messages:
            encrypted_message = encrypt_AES_ECB(message.message, aes_key).decode('utf-8')
            message.message = encrypted_message
            # print(decrypt_AES_ECB(encrypted_message ,aes_key))
        active_thread = Thread.objects.get(id=thread_id)
        active_thread_name = active_thread.name
        rag_docs = active_thread.docs.all()
        base_collection = active_thread.base_collection
        base_collection_name = None if base_collection == None else base_collection.name
        base_collection_type = None if base_collection == None else base_collection.collection_type
        print(f"\ncollections: {collections}\n")
        context = {"chat_threads": threads, "active_thread_id": thread_id, "active_thread_name": active_thread_name, "rag_docs": rag_docs,
                   "base_collection": base_collection, "base_collection_name": base_collection_name, "base_collection_type": base_collection_type, "messages": messages, "threads_preview": threads_preview, 'collections': collections,}
        print(f"\n\n{active_thread_name}\n\n")
        return render(request, 'main/chat.html', context)


@login_required(login_url='users:login')
def create_rag_view(request,):  # Erros front should handle: 1-similar rag_name, 2-avoid creating off limit rag, 3- error when rag_name is not given
    user = request.user
    if request.method == "POST":
        # global vector_db_path
        uploaded_files = request.FILES.getlist('files')
        rag_name = request.POST.get("new-rag-name", None)
        description = None
        base_collection_id = request.POST.get("base-collection-id", None)
        vdb_path = os.path.join(vector_db_path, user.username, f'vdb_{rag_name}')
        docs_path = os.path.join(vdb_path, "docs")
        print(f"base_collection_id: {base_collection_id}")
        if base_collection_id in ["None", None]:
            # create_all_docs_collection()
            create_rag(vdb_path)
            create_folder(docs_path)
            vdb = Thread.objects.create(user=user, name=rag_name, description=description, loc=vdb_path,)
            index = index_builder(vdb_path)
            # all_docs_index = index_builder(all_docs_collection_path)
            for file in uploaded_files:
                file_name = file.name
                print(f"\nfile_name: {file_name} is in progress...\n")
                doc_path = os.path.join(docs_path, file_name)
                doc_path = default_storage.get_available_name(doc_path)
                default_storage.save(doc_path, ContentFile(file.read()))

                document = SimpleDirectoryReader(input_files=[doc_path]).load_data()
                doc_sha256 = hash_file(doc_path)["sha256"]

                doc_obj = Document.objects.create(user=user, name=file_name, public=False,
                                                  description=None, loc=doc_path, sha256= doc_sha256)
                # Create indexes
                for idx, chunked_doc in enumerate(document):
                    doc = llama_index_doc(text=chunked_doc.text, id_=f"{doc_obj.id}_{idx}")
                    index.insert(doc)
                vdb.docs.add(doc_obj)
        else:
            if base_collection_id == "all_docs_collection":
                base_collection = Collection.objects.get(name=all_docs_collection_name)
            else:
                base_collection = Collection.objects.get(id=base_collection_id)
            collection_dir = base_collection.loc
            # copy_folder_contents(collection_dir, vdb_path, "docs")
            vdb = Thread.objects.create(user=user, name=rag_name, description=description, loc=collection_dir, base_collection=base_collection)
        return redirect('main:chat', thread_id=vdb.id)


@login_required(login_url='users:login')
def add_docs_view(request, thread_id):
    user = request.user
    if request.method == "POST":
        global vector_db_path
        uploaded_files = request.FILES.getlist('files')
        thread_id = int(thread_id)
        thread = Thread.objects.get(user=user, id=thread_id)
        rag_name = thread.name
        vdb_path = os.path.join(vector_db_path, user.username, f'vdb_{rag_name}')
        docs_path = os.path.join(vdb_path, "docs")

        # build index
        index = index_builder(vdb_path)
        vdb = Thread.objects.get(user=user, name=rag_name)

        for file in uploaded_files:
            file_name = file.name
            print(f"\nfile_name: {file_name} is in progress...\n")
            doc_path = os.path.join(docs_path, file_name)
            doc_path = default_storage.get_available_name(doc_path)
            default_storage.save(doc_path, ContentFile(file.read()))

            # Load document
            documents = SimpleDirectoryReader(input_files=[doc_path]).load_data()
            doc_sha256 = hash_file(doc_path)["sha256"]

            # Save document info
            doc_obj = Document.objects.create(
                user=user,
                name=file_name,
                public=False,
                description=None,
                loc=doc_path,
                sha256=doc_sha256
            )

            # Insert chunks into index
            for idx, chunked_doc in enumerate(documents):
                doc = llama_index_doc(text=chunked_doc.text, id_=f"{doc_obj.id}_{idx}")
                index.insert(doc)

            vdb.docs.add(doc_obj)

        return redirect('main:chat', thread_id=thread_id)



@login_required(login_url='users:login')
def delete_view(request, thread_id):
    user = request.user
    thread_id = int(thread_id)
    thread = Thread.objects.get(user=user, id=thread_id)
    thread.delete()
    return redirect('main:main_chat')


@login_required(login_url='users:login')    
@user_passes_test(lambda user: user.is_admin() or user.is_advanced_user() or user.is_superuser)
def collections_view(request, collection_id=None,):
    user = request.user
    if request.method == "GET":
        if user.is_admin() or user.is_superuser:
            collections = Collection.objects.all()
        elif user.is_advanced_user():
            collections = Collection.objects.filter(user_created=user)
        collections = collections.annotate(total_docs=Count('docs')).values('id', 'name', 'total_docs', 'user_created', 'collection_type', 'db_type', 'db_connection_string', 'excel_file_paths').order_by('-total_docs')
        if (collection_id is None) and (len(collections) > 0):
            collection_id = int(collections[0]["id"])
            return redirect('main:collection', collection_id=collection_id)
        elif len(collections) == 0:
            context = {"no_collections": True, "active_collection_id": 0,}
            return render(request, 'main/collections.html', context)
        
        collection_id = int(collection_id)
        collection = Collection.objects.get(id=collection_id)
        documents = collection.docs.all()
        context = {"collections": collections, "active_collection_id": collection.id, "active_collection_name": collection.name,
                    "active_collection_creator": collection.user_created, "documents": documents,
                    "active_collection_type": collection.collection_type,
                    "db_schema_analysis": collection.db_schema_analysis,
                    "db_type": collection.db_type,
                    "db_connection_string": collection.db_connection_string,
                    "excel_file_paths": collection.excel_file_paths,
                    "db_extra_knowledge": collection.db_extra_knowledge,}
        return render(request, 'main/collections.html', context)


@login_required(login_url='users:login')   
@user_passes_test(lambda user: user.is_admin() or user.is_advanced_user() or user.is_superuser)
def collection_create_view(request,):
    user = request.user
    if request.method == "POST":
        global collections_path
        collection_name = request.POST.get("new-collection-name", None)
        collection_type = request.POST.get("collection-type", "document")
        
        if collection_name == all_docs_collection_name:
            random_characters = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
            collection_name += random_characters

        allowed_groups = Group.objects.all()  # Can be specified by user while creation
        
        # Handle different collection types
        if collection_type == "document":
            # Original document-based collection logic
            uploaded_files = request.FILES.getlist('files')
            collection_path = os.path.join(collections_path, f'collection_{collection_name}')
            docs_path = os.path.join(collection_path, "docs")
            create_rag(collection_path)
            create_folder(docs_path)
            create_all_docs_collection()

            index = index_builder(collection_path)
            all_docs_index = index_builder(all_docs_collection_path)
            collection_vdb = Collection.objects.create(
                user_created=user, 
                name=collection_name, 
                description=None, 
                loc=collection_path,
                collection_type='document'
            )

            all_docs_collection_vdb = Collection.objects.get(name=all_docs_collection_name)
            collection_vdb.allowed_groups.set(allowed_groups)
            
            for file in uploaded_files:
                file_name = file.name
                print(f"\nfile_name: {file_name} is in progress...\n")
                doc_path = os.path.join(docs_path, file_name)
                doc_path = default_storage.get_available_name(doc_path)
                default_storage.save(doc_path, ContentFile(file.read()))

                document = SimpleDirectoryReader(input_files=[doc_path]).load_data()
                doc_sha256 = hash_file(doc_path)["sha256"]

                doc_obj = Document.objects.create(user=user, name=file_name, public=False,
                                                  description=None, loc=doc_path, sha256=doc_sha256)
                # Create indexes
                if doc_sha256 not in all_docs_collection_vdb.docs.values_list("sha256", flat=True):
                    for idx, chunked_doc in enumerate(document):
                        doc = llama_index_doc(text=chunked_doc.text, id_=f"{doc_obj.id}_{idx}")
                        index.insert(doc)
                        all_docs_index.insert(doc)
                    all_docs_collection_vdb.docs.add(doc_obj)
                    collection_vdb.docs.add(doc_obj)
                else:
                    for idx, chunked_doc in enumerate(document):
                        doc = llama_index_doc(text=chunked_doc.text, id_=f"{doc_obj.id}_{idx}")
                        index.insert(doc)
                    collection_vdb.docs.add(doc_obj)
        
        elif collection_type == "database":
            # Database-backed collection
            from main.utilities.database_utils import (
                analyze_sqlite_schema, analyze_mysql_schema, 
                analyze_postgresql_schema, analyze_mongodb_schema,
                generate_schema_analysis_text
            )
            from main.utilities.variables import llm_url
            
            db_type = request.POST.get("db-type", "sqlite")
            db_extra_knowledge = request.POST.get("db-extra-knowledge", "")
            
            collection_path = os.path.join(collections_path, f'collection_{collection_name}')
            create_folder(collection_path)
            
            # Handle database connection
            if db_type == "sqlite":
                db_file = request.FILES.get('db-file')
                if db_file:
                    db_file_path = os.path.join(collection_path, db_file.name)
                    default_storage.save(db_file_path, ContentFile(db_file.read()))
                    
                    # Analyze schema
                    schema_dict = analyze_sqlite_schema(db_file_path)
                    schema_analysis = generate_schema_analysis_text(schema_dict, llm_url, db_extra_knowledge)
                    
                    collection_vdb = Collection.objects.create(
                        user_created=user,
                        name=collection_name,
                        description=None,
                        loc=collection_path,
                        collection_type='database',
                        db_type=db_type,
                        db_connection_string=db_file_path,
                        db_schema_analysis=schema_analysis,
                        db_extra_knowledge=db_extra_knowledge
                    )
            else:
                # MySQL, PostgreSQL, MongoDB
                db_connection_string = request.POST.get("db-connection-string", "")
                
                try:
                    # Analyze schema based on database type
                    if db_type == "mysql":
                        schema_dict = analyze_mysql_schema(db_connection_string)
                    elif db_type == "postgresql":
                        schema_dict = analyze_postgresql_schema(db_connection_string)
                    elif db_type == "mongodb":
                        schema_dict = analyze_mongodb_schema(db_connection_string)
                    else:
                        schema_dict = {"error": "Unsupported database type"}
                    
                    schema_analysis = generate_schema_analysis_text(schema_dict, llm_url, db_extra_knowledge)
                    
                    collection_vdb = Collection.objects.create(
                        user_created=user,
                        name=collection_name,
                        description=None,
                        loc=collection_path,
                        collection_type='database',
                        db_type=db_type,
                        db_connection_string=db_connection_string,
                        db_schema_analysis=schema_analysis,
                        db_extra_knowledge=db_extra_knowledge
                    )
                except Exception as e:
                    print(f"Error analyzing database schema: {e}")
                    # Create collection anyway with error message
                    collection_vdb = Collection.objects.create(
                        user_created=user,
                        name=collection_name,
                        description=None,
                        loc=collection_path,
                        collection_type='database',
                        db_type=db_type,
                        db_connection_string=db_connection_string,
                        db_schema_analysis=f"Error analyzing schema: {str(e)}",
                        db_extra_knowledge=db_extra_knowledge
                    )
            
            collection_vdb.allowed_groups.set(allowed_groups)
        
        elif collection_type == "excel":
            # Excel/CSV-backed collection
            from main.utilities.database_utils import analyze_excel_files, generate_schema_analysis_text
            from main.utilities.variables import llm_url
            
            excel_files = request.FILES.getlist('excel-files')[:5]  # Max 5 files
            excel_extra_knowledge = request.POST.get("excel-extra-knowledge", "")
            
            collection_path = os.path.join(collections_path, f'collection_{collection_name}')
            create_folder(collection_path)
            
            # Save Excel/CSV files
            file_paths = []
            for file in excel_files:
                file_path = os.path.join(collection_path, file.name)
                default_storage.save(file_path, ContentFile(file.read()))
                file_paths.append(file_path)
            
            # Analyze schema
            schema_dict = analyze_excel_files(file_paths)
            schema_analysis = generate_schema_analysis_text(schema_dict, llm_url, excel_extra_knowledge)
            
            collection_vdb = Collection.objects.create(
                user_created=user,
                name=collection_name,
                description=None,
                loc=collection_path,
                collection_type='excel',
                excel_file_paths=file_paths,
                db_schema_analysis=schema_analysis,
                db_extra_knowledge=excel_extra_knowledge
            )
            
            collection_vdb.allowed_groups.set(allowed_groups)

        return redirect('main:collection', collection_id=collection_vdb.id)


@login_required(login_url='users:login')
@user_passes_test(lambda user: user.is_admin() or user.is_advanced_user() or user.is_superuser)
def collection_reindex_view(request, collection_id):
    from django.http import JsonResponse
    
    user = request.user
    collection_id = int(collection_id)
    collection = Collection.objects.get(id=collection_id)
    
    # Check permissions
    if user.is_advanced_user() and not (user.is_admin() or user.is_superuser):
        if collection.user_created != user:
            return redirect('main:main_collection')
    
    # Only reindex database and Excel collections
    if collection.collection_type not in ['database', 'excel']:
        return redirect('main:collection', collection_id=collection_id)
    
    from main.utilities.database_utils import (
        analyze_sqlite_schema, analyze_mysql_schema,
        analyze_postgresql_schema, analyze_mongodb_schema,
        analyze_excel_files, generate_schema_analysis_text
    )
    from main.utilities.variables import llm_url
    
    # Store the old schema in case of failure
    old_schema_analysis = collection.db_schema_analysis
    
    try:
        if collection.collection_type == 'database':
            db_type = collection.db_type
            db_connection_string = collection.db_connection_string
            db_extra_knowledge = collection.db_extra_knowledge or ""
            
            # Re-analyze schema based on database type
            if db_type == 'sqlite':
                schema_dict = analyze_sqlite_schema(db_connection_string)
            elif db_type == 'mysql':
                schema_dict = analyze_mysql_schema(db_connection_string)
            elif db_type == 'postgresql':
                schema_dict = analyze_postgresql_schema(db_connection_string)
            elif db_type == 'mongodb':
                schema_dict = analyze_mongodb_schema(db_connection_string)
            else:
                schema_dict = {"error": "Unsupported database type"}
            
            # Generate new schema analysis
            schema_analysis = generate_schema_analysis_text(schema_dict, llm_url, db_extra_knowledge)
            
            # Check if schema analysis contains error message
            if schema_analysis and "Error generating schema analysis" in schema_analysis:
                # Restore old schema and return error
                print(f"LLM error during reindexing: Schema analysis contains error message")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'LLM server unavailable. Previous schema preserved.'}, status=500)
                return redirect('main:collection', collection_id=collection_id)
            
            # Update collection only if successful
            collection.db_schema_analysis = schema_analysis
            collection.save()
            
        elif collection.collection_type == 'excel':
            file_paths = collection.excel_file_paths or []
            excel_extra_knowledge = collection.db_extra_knowledge or ""
            
            # Re-analyze Excel files
            schema_dict = analyze_excel_files(file_paths)
            schema_analysis = generate_schema_analysis_text(schema_dict, llm_url, excel_extra_knowledge)
            
            # Check if schema analysis contains error message
            if schema_analysis and "Error generating schema analysis" in schema_analysis:
                # Restore old schema and return error
                print(f"LLM error during reindexing: Schema analysis contains error message")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'LLM server unavailable. Previous schema preserved.'}, status=500)
                return redirect('main:collection', collection_id=collection_id)
            
            # Update collection only if successful
            collection.db_schema_analysis = schema_analysis
            collection.save()
        
        print(f"Collection '{collection.name}' schema successfully reindexed.")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
    except Exception as e:
        # Preserve old schema on any error
        print(f"Error reindexing collection schema: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return redirect('main:collection', collection_id=collection_id)


@login_required(login_url='users:login')
@user_passes_test(lambda user: user.is_admin() or user.is_advanced_user() or user.is_superuser)
def collection_delete_view(request, collection_id):
    user = request.user
    collection_id = int(collection_id)
    collection = Collection.objects.get(id=collection_id)  # Now each Admin can delete any of collections
    if user.is_admin() or user.is_superuser or (user.is_advanced_user() and collection.user_created == user):
        collection.delete()
    return redirect('main:main_collection')


@login_required(login_url='users:login')
@user_passes_test(lambda user: user.is_admin() or user.is_advanced_user() or user.is_superuser)
def collection_download_file(request, collection_id, file_index):
    from django.http import FileResponse, Http404
    import mimetypes
    
    user = request.user
    collection_id = int(collection_id)
    file_index = int(file_index)
    
    try:
        collection = Collection.objects.get(id=collection_id)
        
        # Check permissions
        if user.is_advanced_user() and not (user.is_admin() or user.is_superuser):
            if collection.user_created != user:
                raise Http404("File not found")
        
        # Determine file path based on collection type
        if collection.collection_type == 'excel':
            if not collection.excel_file_paths or file_index >= len(collection.excel_file_paths):
                raise Http404("File not found")
            file_path = collection.excel_file_paths[file_index]
        elif collection.collection_type == 'database' and collection.db_type == 'sqlite':
            file_path = collection.db_connection_string
        else:
            raise Http404("File not found")
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise Http404("File not found")
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = 'application/octet-stream'
        
        # Open and return file
        file_name = os.path.basename(file_path)
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response
        
    except Collection.DoesNotExist:
        raise Http404("Collection not found")
    except Exception as e:
        print(f"Error downloading file: {e}")
        raise Http404("File not found")


@login_required(login_url='users:login')
@user_passes_test(lambda user: user.is_admin() or user.is_advanced_user() or user.is_superuser)
def collection_add_docs_view(request, collection_id):
    user = request.user
    if request.method == "POST":
        global collections_path
        uploaded_files = request.FILES.getlist('files')
        collection_id = int(collection_id)
        collection_vdb = Collection.objects.get(id=collection_id)  # Now each Admin can add to any of collections
        all_docs_collection_vdb = Collection.objects.get(name=all_docs_collection_name)
        if user.is_advanced_user() and not (user.is_admin() or user.is_superuser):
            if collection_vdb.user_created != user:
                return redirect('main:main_collection')
        collection_name = collection_vdb.name
        collection_path = os.path.join(collections_path, f'collection_{collection_name}')
        docs_path = os.path.join(collection_path, "docs")
        index = index_builder(collection_path)
        create_all_docs_collection()
        all_docs_index = index_builder(all_docs_collection_path)
        for file in uploaded_files:
            file_name = file.name
            print(f"\nfile_name: {file_name} is in progress...\n")
            doc_path = os.path.join(docs_path, file_name)
            doc_path = default_storage.get_available_name(doc_path)
            default_storage.save(doc_path, ContentFile(file.read()))

            # document = loader.load(file_path=Path(doc_path), metadata=False)
            document = SimpleDirectoryReader(input_files=[doc_path]).load_data()
            doc_sha256 = hash_file(doc_path)["sha256"]

            doc_obj = Document.objects.create(user=user, name=file_name, public=False,
                                              description=None, loc=doc_path, sha256=doc_sha256)
            # Create indexes
            if doc_sha256 not in all_docs_collection_vdb.docs.values_list("sha256", flat=True):
                for idx, chunked_doc in enumerate(document):
                    doc = llama_index_doc(text=chunked_doc.text, id_=f"{doc_obj.id}_{idx}")
                    index.insert(doc)
                    all_docs_index.insert(doc)
                all_docs_collection_vdb.docs.add(doc_obj)
                collection_vdb.docs.add(doc_obj)
            else:
                for idx, chunked_doc in enumerate(document):
                    doc = llama_index_doc(text=chunked_doc.text, id_=f"{doc_obj.id}_{idx}")
                    index.insert(doc)
                collection_vdb.docs.add(doc_obj)

        return redirect('main:collection', collection_id=collection_id)