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
from django.db.models import Max, Count, Q
from main.utilities.helper_functions import create_folder, get_first_words, copy_folder_contents, hash_file
from main.utilities.RAG import create_rag, index_builder, create_all_docs_collection
from pathlib import Path
from django.conf import settings
import os, shutil, random, string
from llama_index.core import SimpleDirectoryReader
from llama_index.core import SummaryIndex, Document as llama_index_doc
from main.utilities.encryption import *
import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import functools
import logging
import sys
import time
import gc

# Configure logging for indexing (not AJAX spam)
indexing_logger = logging.getLogger('indexing')
indexing_logger.setLevel(logging.INFO)
if not indexing_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('\n[INDEXING] %(message)s'))
    indexing_logger.addHandler(handler)

# Diagnostic: Check what PDF libraries are available
def check_pdf_libraries():
    """Log which PDF parsing libraries are available"""
    libs = []
    try:
        import PyPDF2
        libs.append(f"PyPDF2 v{PyPDF2.__version__}")
    except ImportError:
        pass
    
    try:
        import pymupdf
        libs.append(f"PyMuPDF v{pymupdf.__version__}")
    except ImportError:
        try:
            import fitz
            libs.append(f"PyMuPDF (fitz) v{fitz.__version__}")
        except ImportError:
            pass
    
    try:
        import pdfminer
        libs.append(f"pdfminer v{pdfminer.__version__}")
    except ImportError:
        pass
    
    try:
        import pdfplumber
        libs.append(f"pdfplumber v{pdfplumber.__version__}")
    except ImportError:
        pass
    
    if libs:
        indexing_logger.info(f"PDF libraries available: {', '.join(libs)}")
    else:
        indexing_logger.warning("⚠ No PDF libraries detected!")
    
    return libs

# Run diagnostic on import
_pdf_libs = check_pdf_libraries()

# Use absolute paths for cross-platform compatibility
vector_db_path = os.path.join(settings.BASE_DIR, "vector_dbs")
collections_path = os.path.join(settings.BASE_DIR, "collections")
all_docs_collection_name = "ALL_DOCS_COLLECTION"
all_docs_collection_path = os.path.join(collections_path, all_docs_collection_name)

# CRITICAL: Print path configuration for debugging
print("\n" + "="*70)
print("PATH CONFIGURATION (views.py startup)")
print("="*70)
print(f"BASE_DIR: {settings.BASE_DIR}")
print(f"collections_path: {collections_path}")
print(f"collections_path is absolute: {os.path.isabs(collections_path)}")
print(f"collections_path exists: {os.path.exists(collections_path)}")
print(f"Current working directory: {os.getcwd()}")
print("="*70 + "\n")

# CRITICAL: Ensure base directories exist at startup
for base_path in [vector_db_path, collections_path]:
    if not os.path.exists(base_path):
        print(f"[STARTUP] Creating missing directory: {base_path}")
        try:
            os.makedirs(base_path, exist_ok=True)
            print(f"[STARTUP] ✓ Created: {base_path}")
        except Exception as e:
            print(f"[STARTUP] ✗ FAILED to create {base_path}: {e}")
    else:
        print(f"[STARTUP] ✓ Directory exists: {base_path}")

# Log paths on startup
import logging
_startup_logger = logging.getLogger('main.indexing')
_startup_logger.info(f"=== Path Configuration ===")
_startup_logger.info(f"BASE_DIR: {settings.BASE_DIR}")
_startup_logger.info(f"vector_db_path: {vector_db_path}")
_startup_logger.info(f"collections_path: {collections_path}")
_startup_logger.info(f"all_docs_collection_path: {all_docs_collection_path}")
_startup_logger.info(f"=========================")

# Disable signal alarm in LlamaIndex - it doesn't work in Django threads on Linux
if sys.platform.startswith('linux'):
    try:
        # Monkey-patch signal to prevent LlamaIndex from using it in threads
        import signal as _signal_module
        _original_signal = _signal_module.signal
        _original_alarm = _signal_module.alarm
        
        def _patched_signal(signalnum, handler):
            import threading
            if threading.current_thread() is threading.main_thread():
                return _original_signal(signalnum, handler)
            return None
        
        def _patched_alarm(time):
            import threading
            if threading.current_thread() is threading.main_thread():
                return _original_alarm(time)
            return 0
        
        _signal_module.signal = _patched_signal
        _signal_module.alarm = _patched_alarm
        indexing_logger.info("✓ Signal module patched for Linux")
    except Exception as e:
        indexing_logger.warning(f"Could not patch signal module: {e}")

# Cross-platform timeout handler for document loading
class TimeoutException(Exception):
    pass

def load_document_with_timeout(file_path, timeout_seconds=60):
    """
    Load a document with timeout protection.
    Uses temporary file for IPC to avoid queue serialization issues.
    Uses separate module for subprocess to avoid Django import issues on Windows.
    """
    import multiprocessing
    import tempfile
    import pickle
    from main.utilities.document_loader import load_document_subprocess
    
    # Get file metadata for logging
    file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
    ext = os.path.splitext(file_path)[1].lower()
    
    # Create temporary file for IPC
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as tmp:
        result_file = tmp.name
    
    try:
        process = multiprocessing.Process(target=load_document_subprocess, args=(file_path, result_file))
        
        indexing_logger.info(f"📄 File: {os.path.basename(file_path)} ({file_size:.2f} MB, {ext})")
        indexing_logger.info(f"⏳ Starting subprocess to load document...")
        start_time = time.time()
        process.start()
        
        # Poll with progress updates
        elapsed = 0
        check_interval = 5
        while process.is_alive() and elapsed < timeout_seconds:
            time.sleep(check_interval)
            elapsed = time.time() - start_time
            if process.is_alive() and elapsed < timeout_seconds:
                indexing_logger.info(f"   ... still loading ({int(elapsed)}s elapsed)")
        
        if process.is_alive():
            # Still running after timeout - KILL IT
            elapsed = time.time() - start_time
            indexing_logger.warning(f"⚠ TIMEOUT after {int(elapsed)}s - KILLING process")
            indexing_logger.warning(f"   The subprocess is stuck (not responding)")
            process.terminate()
            time.sleep(2)
            if process.is_alive():
                indexing_logger.warning(f"   Process still alive - using SIGKILL")
                process.kill()
            process.join(timeout=5)
            raise TimeoutException(f"Document loading timed out after {timeout_seconds} seconds")
        
        # Process finished - read results from file
        process.join()  # Ensure process is fully terminated
        elapsed = time.time() - start_time
        
        if os.path.exists(result_file) and os.path.getsize(result_file) > 0:
            try:
                with open(result_file, 'rb') as f:
                    status, result = pickle.load(f)
                
                if status == 'success':
                    chunks = len(result) if result else 0
                    indexing_logger.info(f"✓ SUCCESS in {elapsed:.1f}s ({chunks} chunks)")
                    return result
                else:
                    indexing_logger.error(f"✗ FAILED in {elapsed:.1f}s")
                    indexing_logger.error(f"   Error details:\n{result}")
                    raise Exception(result)
            except Exception as e:
                if 'status' in locals():
                    raise  # Re-raise if we already parsed the error above
                else:
                    indexing_logger.error(f"✗ Could not read results: {e}")
                    raise Exception(f"Failed to read subprocess results: {e}")
        else:
            indexing_logger.error(f"✗ Process terminated without result (exit code: {process.exitcode})")
            raise Exception(f"Process terminated without result (exit code: {process.exitcode})")
    
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(result_file):
                os.unlink(result_file)
        except:
            pass

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
        # Get or retrieve aes_key from session
        if request.method == "POST":
            encrypted_aes_key = request.POST.get("encrypted_aes_key", None)
            if encrypted_aes_key:
                aes_key = decrypt_aes_key(encrypted_aes_key)
                # Store in session as base64 string (bytes are not JSON serializable)
                request.session['aes_key'] = base64.b64encode(aes_key).decode('utf-8')
                request.session.save()
            else:
                # Fallback to session key if POST doesn't contain it
                aes_key_b64 = request.session.get('aes_key', None)
                aes_key = base64.b64decode(aes_key_b64) if aes_key_b64 else None
        else:
            # GET request - retrieve from session and decode from base64
            aes_key_b64 = request.session.get('aes_key', None)
            aes_key = base64.b64decode(aes_key_b64) if aes_key_b64 else None
        threads = Thread.objects.filter(user=user).annotate(last_message_timestamp=Max('chatmessage__timestamp'))
        threads = threads.order_by('-last_message_timestamp')
        if len(threads) == 0:
            # Check whether All docs collection exists in Collection table and filesystem
            create_all_docs_collection()
            collections = Collection.objects.exclude(name=all_docs_collection_name).values('id', 'name')
            from main.utilities.variables import model_name
            context = {"no_threads": True, "active_thread_id": 0, 'collections': collections, 'model_name': model_name}
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
            from main.utilities.variables import model_name
            context = {"chat_threads": threads, "threads_preview": threads_preview, 'collections': collections, "no_active_thread": True,
                       "no_threads": True, "active_thread_id": 0, 'model_name': model_name}
            return render(request, 'main/chat.html', context)
        thread_id = int(thread_id)
        messages = ChatMessage.objects.filter(user=user, thread=thread_id)
        # Encrypt messages if aes_key is available
        if aes_key:
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
        base_collection_db_type = None if base_collection == None else base_collection.db_type
        
        # Get collection documents for document-type collections
        collection_docs = None
        if base_collection and base_collection.collection_type == 'document':
            collection_docs = base_collection.docs.all()
        
        from main.utilities.variables import model_name
        print(f"\ncollections: {collections}\n")
        context = {"chat_threads": threads, "active_thread_id": thread_id, "active_thread_name": active_thread_name, "rag_docs": rag_docs,
                   "base_collection": base_collection, "base_collection_name": base_collection_name, "base_collection_type": base_collection_type, "base_collection_db_type": base_collection_db_type, 
                   "collection_docs": collection_docs, "messages": messages, "threads_preview": threads_preview, 'collections': collections, 'model_name': model_name}
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
        
        # Initialize progress tracking in session
        total_files = len(uploaded_files)
        request.session['indexing_progress'] = {'current': 0, 'total': total_files, 'filename': ''}
        request.session.save()
        indexing_logger.info(f"\\n{'='*60}\\nStarting indexing: {total_files} files\\n{'='*60}")

        for file_idx, file in enumerate(uploaded_files, 1):
            file_name = file.name
            # Update progress
            request.session['indexing_progress'] = {'current': file_idx, 'total': total_files, 'filename': file_name}
            request.session.save()
            # Minimal console output
            doc_path = os.path.join(docs_path, file_name)
            doc_path = default_storage.get_available_name(doc_path)
            default_storage.save(doc_path, ContentFile(file.read()))

            # Load document with timeout protection
            indexing_logger.info(f"Processing file {file_idx}/{total_files}: {file_name}")
            try:
                documents = load_document_with_timeout(doc_path, timeout_seconds=60)
            except TimeoutException as e:
                indexing_logger.warning(f"⚠ SKIPPED (timeout): {file_name}")
                continue
            except Exception as e:
                indexing_logger.error(f"✗ SKIPPED (error): {file_name} - {str(e)}")
                continue
            
            # Document loaded successfully, now index it
            try:
                indexing_logger.info(f"   Creating document object and indexing...")
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
                indexing_logger.info(f"   ✓ Document object created (ID: {doc_obj.id})")

                # Insert chunks into index
                indexing_logger.info(f"   Inserting {len(documents)} chunks into index...")
                for idx, chunked_doc in enumerate(documents):
                    doc = llama_index_doc(text=chunked_doc.text, id_=f"{doc_obj.id}_{idx}")
                    index.insert(doc)

                vdb.docs.add(doc_obj)
                indexing_logger.info(f"✓ COMPLETED: {file_name}")
                
            except Exception as e:
                indexing_logger.error(f"✗ INDEXING FAILED for {file_name}: {str(e)}")
                import traceback
                indexing_logger.error(traceback.format_exc())
                # Delete the file if indexing failed
                if os.path.exists(doc_path):
                    os.remove(doc_path)
                continue
        
        # Clear progress after completion
        request.session['indexing_progress'] = None
        request.session.save()
        indexing_logger.info(f"\n{'='*60}\n✓ INDEXING COMPLETED\n{'='*60}\n")

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
            
            # Log collection creation
            indexing_logger.info(f"[collection_create_view] Creating new collection: {collection_name}")
            indexing_logger.info(f"[collection_create_view] BASE_DIR: {settings.BASE_DIR}")
            indexing_logger.info(f"[collection_create_view] collections_path: {collections_path}")
            indexing_logger.info(f"[collection_create_view] Collection path: {collection_path}")
            indexing_logger.info(f"[collection_create_view] Collection path is absolute: {os.path.isabs(collection_path)}")
            indexing_logger.info(f"[collection_create_view] Docs path: {docs_path}")
            
            # Create collection directory structure
            try:
                indexing_logger.info(f"[collection_create_view] Calling create_rag({collection_path})...")
                create_rag(collection_path)
                indexing_logger.info(f"[collection_create_view] ✓ create_rag completed")
                indexing_logger.info(f"[collection_create_view] Collection directory exists after create_rag: {os.path.exists(collection_path)}")
                if os.path.exists(collection_path):
                    indexing_logger.info(f"[collection_create_view] Contents: {os.listdir(collection_path)}")
                
                create_folder(docs_path)
                indexing_logger.info(f"[collection_create_view] ✓ docs folder created")
                indexing_logger.info(f"[collection_create_view] Docs directory exists: {os.path.exists(docs_path)}")
            except Exception as e:
                indexing_logger.error(f"[collection_create_view] ✗ Failed to create collection structure: {e}")
                import traceback
                indexing_logger.error(traceback.format_exc())
                return JsonResponse({'error': f'Failed to create collection: {e}'}, status=500)
            
            create_all_docs_collection()

            indexing_logger.info(f"[collection_create_view] Calling index_builder({collection_path})...")
            index = index_builder(collection_path)
            indexing_logger.info(f"[collection_create_view] ✓ index_builder completed, index type: {type(index)}")
            
            # Verify SQLite database was created
            sqlite_path = os.path.join(collection_path, "chroma.sqlite3")
            indexing_logger.info(f"[collection_create_view] Checking for SQLite database...")
            indexing_logger.info(f"[collection_create_view] Expected path: {sqlite_path}")
            indexing_logger.info(f"[collection_create_view] SQLite exists: {os.path.exists(sqlite_path)}")
            if os.path.exists(collection_path):
                indexing_logger.info(f"[collection_create_view] Collection directory contents: {os.listdir(collection_path)}")
            
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
            
            # Initialize progress tracking in session
            total_files = len(uploaded_files)
            request.session['indexing_progress'] = {'current': 0, 'total': total_files, 'filename': ''}
            request.session.save()
            print(f"[Progress] Initialized: 0/{total_files}")
            
            for idx, file in enumerate(uploaded_files, 1):
                file_name = file.name
                # Update progress
                request.session['indexing_progress'] = {'current': idx, 'total': total_files, 'filename': file_name}
                request.session.save()
                
                # Minimal console output
                doc_path = os.path.join(docs_path, file_name)
                doc_path = default_storage.get_available_name(doc_path)
                default_storage.save(doc_path, ContentFile(file.read()))

                # Load document with timeout protection
                indexing_logger.info(f"Processing file {idx}/{total_files}: {file_name}")
                try:
                    document = load_document_with_timeout(doc_path, timeout_seconds=60)
                except TimeoutException as e:
                    indexing_logger.warning(f"⚠ SKIPPED (timeout): {file_name}")
                    continue
                except Exception as e:
                    indexing_logger.error(f"✗ SKIPPED (error): {file_name} - {str(e)}")
                    continue
                
                # Document loaded successfully, now index it
                try:
                    indexing_logger.info(f"   Creating document object and indexing...")
                    doc_sha256 = hash_file(doc_path)["sha256"]

                    doc_obj = Document.objects.create(user=user, name=file_name, public=False,
                                                      description=None, loc=doc_path, sha256=doc_sha256)
                    indexing_logger.info(f"   ✓ Document object created (ID: {doc_obj.id})")
                    
                    # Create indexes - FIX: Batch insertions and separate index operations to avoid SQLite contention on Linux
                    indexing_logger.info(f"   Preparing {len(document)} chunks for indexing...")
                    indexing_logger.info(f"   Index object: {index}")
                    indexing_logger.info(f"   All_docs_index object: {all_docs_index}")
                    
                    # Create all LlamaIndex documents first
                    docs_to_index = []
                    for idx_chunk, chunked_doc in enumerate(document):
                        doc = llama_index_doc(text=chunked_doc.text, id_=f"{doc_obj.id}_{idx_chunk}")
                        docs_to_index.append(doc)
                    indexing_logger.info(f"   ✓ Created {len(docs_to_index)} document objects")
                    
                    if doc_sha256 not in all_docs_collection_vdb.docs.values_list("sha256", flat=True):
                        # Insert all chunks into collection index first (batch operation with micro-batches for Linux)
                        indexing_logger.info(f"   Inserting {len(docs_to_index)} chunks into COLLECTION index...")
                        MICRO_BATCH_SIZE = 3  # Insert 3 chunks at a time to prevent resource exhaustion
                        for i in range(0, len(docs_to_index), MICRO_BATCH_SIZE):
                            batch_end = min(i + MICRO_BATCH_SIZE, len(docs_to_index))
                            indexing_logger.info(f"   Micro-batch {i//MICRO_BATCH_SIZE + 1}: chunks {i+1}-{batch_end}")
                            
                            for idx_chunk in range(i, batch_end):
                                doc = docs_to_index[idx_chunk]
                                indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] Collection insert...")
                                try:
                                    index.insert(doc)
                                    indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] ✓")
                                except Exception as e:
                                    indexing_logger.error(f"      ✗ Collection insert failed: {e}")
                                    raise
                            
                            # Force garbage collection and small pause after each micro-batch
                            if sys.platform.startswith('linux'):
                                gc.collect()
                                time.sleep(0.1)
                                indexing_logger.info(f"   Micro-batch complete, memory cleared")
                        
                        indexing_logger.info(f"   ✓ All chunks inserted into collection index")
                        
                        # Give ChromaDB/SQLite time to commit on Linux
                        if sys.platform.startswith('linux'):
                            indexing_logger.info(f"   [Linux] Pausing 1s for SQLite commit...")
                            time.sleep(1.0)
                            gc.collect()
                        
                        # Verify collection directory and SQLite database
                        indexing_logger.info(f"   Verifying collection persistence...")
                        sqlite_path = os.path.join(collection_path, "chroma.sqlite3")
                        if os.path.exists(sqlite_path):
                            indexing_logger.info(f"   ✓ SQLite database exists: {os.path.getsize(sqlite_path)} bytes")
                        else:
                            indexing_logger.error(f"   ✗ SQLite database NOT FOUND at: {sqlite_path}")
                            indexing_logger.error(f"   Collection directory contents: {os.listdir(collection_path) if os.path.exists(collection_path) else 'DIR NOT FOUND'}")
                        
                        # Verify collection directory and SQLite database                        indexing_logger.info(f"   Verifying collection persistence...")
                        sqlite_path = os.path.join(collection_path, "chroma.sqlite3")
                        if os.path.exists(sqlite_path):
                            indexing_logger.info(f"   ✓ SQLite database exists: {os.path.getsize(sqlite_path)} bytes")
                        else:
                            indexing_logger.error(f"   ✗ SQLite database NOT FOUND at: {sqlite_path}")
                            indexing_logger.error(f"   Collection directory contents: {os.listdir(collection_path) if os.path.exists(collection_path) else 'DIR NOT FOUND'}")
                        
                        # Now insert all chunks into all_docs index (separate batch)
                        indexing_logger.info(f"   Inserting {len(docs_to_index)} chunks into ALL_DOCS index...")
                        for i in range(0, len(docs_to_index), MICRO_BATCH_SIZE):
                            batch_end = min(i + MICRO_BATCH_SIZE, len(docs_to_index))
                            indexing_logger.info(f"   Micro-batch {i//MICRO_BATCH_SIZE + 1}: chunks {i+1}-{batch_end}")
                            
                            for idx_chunk in range(i, batch_end):
                                doc = docs_to_index[idx_chunk]
                                indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] All_docs insert...")
                                try:
                                    all_docs_index.insert(doc)
                                    indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] ✓")
                                except Exception as e:
                                    indexing_logger.error(f"      ✗ All_docs insert failed: {e}")
                                    raise
                            
                            # Force garbage collection and small pause after each micro-batch
                            if sys.platform.startswith('linux'):
                                gc.collect()
                                time.sleep(0.1)
                                indexing_logger.info(f"   Micro-batch complete, memory cleared")
                        
                        indexing_logger.info(f"   ✓ All chunks inserted into all_docs index")
                        
                        # Verify all_docs persistence
                        all_docs_sqlite = os.path.join(all_docs_collection_path, "chroma.sqlite3")
                        if os.path.exists(all_docs_sqlite):
                            indexing_logger.info(f"   ✓ All_docs SQLite: {os.path.getsize(all_docs_sqlite)} bytes")
                        
                        # Verify all_docs persistence
                        all_docs_sqlite = os.path.join(all_docs_collection_path, "chroma.sqlite3")
                        if os.path.exists(all_docs_sqlite):
                            indexing_logger.info(f"   ✓ All_docs SQLite: {os.path.getsize(all_docs_sqlite)} bytes")
                        
                        # Force ChromaDB sync on Linux by querying count
                        if sys.platform.startswith('linux'):
                            indexing_logger.info(f"   [Linux] Ensuring ChromaDB sync...")
                            try:
                                if hasattr(index, '_chroma_collection'):
                                    count = index._chroma_collection.count()
                                    indexing_logger.info(f"   ✓ Collection has {count} vectors in ChromaDB")
                                if hasattr(all_docs_index, '_chroma_collection'):
                                    all_count = all_docs_index._chroma_collection.count()
                                    indexing_logger.info(f"   ✓ All_docs has {all_count} vectors in ChromaDB")
                                time.sleep(0.5)  # Give filesystem time to sync
                            except Exception as e:
                                indexing_logger.warning(f"   ⚠ ChromaDB sync check failed: {e}")
                        
                        all_docs_collection_vdb.docs.add(doc_obj)
                        collection_vdb.docs.add(doc_obj)
                        indexing_logger.info(f"   ✓ Indexed to collection and all_docs")
                    else:
                        # Only insert into collection index
                        indexing_logger.info(f"   Document already in all_docs, inserting {len(docs_to_index)} chunks into collection only...")
                        MICRO_BATCH_SIZE = 3
                        for i in range(0, len(docs_to_index), MICRO_BATCH_SIZE):
                            batch_end = min(i + MICRO_BATCH_SIZE, len(docs_to_index))
                            indexing_logger.info(f"   Micro-batch {i//MICRO_BATCH_SIZE + 1}: chunks {i+1}-{batch_end}")
                            
                            for idx_chunk in range(i, batch_end):
                                doc = docs_to_index[idx_chunk]
                                indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] Collection insert...")
                                try:
                                    index.insert(doc)
                                    indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] ✓")
                                except Exception as e:
                                    indexing_logger.error(f"      ✗ Insert failed: {e}")
                                    raise
                            
                            # Force garbage collection and small pause after each micro-batch
                            if sys.platform.startswith('linux'):
                                gc.collect()
                                time.sleep(0.1)
                                indexing_logger.info(f"   Micro-batch complete, memory cleared")
                        
                        indexing_logger.info(f"   ✓ All chunks inserted into collection")
                        
                        # Verify collection persistence
                        indexing_logger.info(f"   Verifying collection persistence...")
                        sqlite_path = os.path.join(collection_path, "chroma.sqlite3")
                        if os.path.exists(sqlite_path):
                            indexing_logger.info(f"   ✓ SQLite database exists: {os.path.getsize(sqlite_path)} bytes")
                        else:
                            indexing_logger.error(f"   ✗ SQLite database NOT FOUND at: {sqlite_path}")
                            indexing_logger.error(f"   Collection directory contents: {os.listdir(collection_path) if os.path.exists(collection_path) else 'DIR NOT FOUND'}")
                        
                        
                        # Verify collection persistence
                        indexing_logger.info(f"   Verifying collection persistence...")
                        sqlite_path = os.path.join(collection_path, "chroma.sqlite3")
                        if os.path.exists(sqlite_path):
                            indexing_logger.info(f"   ✓ SQLite database exists: {os.path.getsize(sqlite_path)} bytes")
                        else:
                            indexing_logger.error(f"   ✗ SQLite database NOT FOUND at: {sqlite_path}")
                            indexing_logger.error(f"   Collection directory contents: {os.listdir(collection_path) if os.path.exists(collection_path) else 'DIR NOT FOUND'}")
                        
                        # Force ChromaDB sync on Linux by querying count
                        if sys.platform.startswith('linux'):
                            indexing_logger.info(f"   [Linux] Ensuring ChromaDB sync...")
                            try:
                                if hasattr(index, '_chroma_collection'):
                                    count = index._chroma_collection.count()
                                    indexing_logger.info(f"   ✓ Collection has {count} vectors in ChromaDB")
                                time.sleep(0.5)  # Give filesystem time to sync
                            except Exception as e:
                                indexing_logger.warning(f"   ⚠ ChromaDB sync check failed: {e}")
                        
                        collection_vdb.docs.add(doc_obj)
                        indexing_logger.info(f"   ✓ Indexed to collection")
                    
                    # Verify document was added
                    doc_count = collection_vdb.docs.count()
                    indexing_logger.info(f"   Collection now has {doc_count} documents")
                    indexing_logger.info(f"✓ COMPLETED: {file_name}")
                    
                except Exception as e:
                    indexing_logger.error(f"✗ INDEXING FAILED for {file_name}: {str(e)}")
                    import traceback
                    indexing_logger.error(traceback.format_exc())
                    # Delete the file if indexing failed
                    if os.path.exists(doc_path):
                        os.remove(doc_path)
                    continue
            
            # Clear progress after completion
            request.session['indexing_progress'] = None
            request.session.save()
            indexing_logger.info(f"\n{'='*60}\n✓ INDEXING COMPLETED\n{'='*60}\n")
        
        elif collection_type == "database":
            # Database-backed collection
            from main.utilities.database_utils import (
                analyze_sqlite_schema, analyze_mysql_schema, 
                analyze_postgresql_schema, analyze_mongodb_schema, analyze_sqlserver_schema,
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
                # MySQL, PostgreSQL, MongoDB, SQL Server
                # Build connection string from form fields
                db_host = request.POST.get("db-host", "localhost")
                db_port = request.POST.get("db-port", "")
                db_name = request.POST.get("db-name", "")
                db_username = request.POST.get("db-username", "")
                db_password = request.POST.get("db-password", "")
                
                # Construct connection string based on database type
                if db_type == "mysql":
                    port = db_port or "3306"
                    db_connection_string = f"mysql://{db_username}:{db_password}@{db_host}:{port}/{db_name}"
                elif db_type == "postgresql":
                    port = db_port or "5432"
                    db_connection_string = f"postgresql://{db_username}:{db_password}@{db_host}:{port}/{db_name}"
                elif db_type == "mongodb":
                    port = db_port or "27017"
                    db_connection_string = f"mongodb://{db_username}:{db_password}@{db_host}:{port}/{db_name}"
                elif db_type == "sqlserver":
                    # URL encode backslash in server name (e.g., localhost\SQLEXPRESS)
                    from urllib.parse import quote
                    encoded_host = quote(db_host, safe='')
                    # If username is empty, use Windows Authentication
                    if not db_username:
                        db_connection_string = f"mssql+pyodbc://windows_auth@{encoded_host}/{db_name}?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Trusted_Connection=yes"
                    else:
                        db_connection_string = f"mssql+pyodbc://{db_username}:{db_password}@{encoded_host}/{db_name}?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
                else:
                    db_connection_string = ""
                
                try:
                    # Analyze schema based on database type
                    if db_type == "mysql":
                        schema_dict = analyze_mysql_schema(db_connection_string)
                    elif db_type == "postgresql":
                        schema_dict = analyze_postgresql_schema(db_connection_string)
                    elif db_type == "mongodb":
                        schema_dict = analyze_mongodb_schema(db_connection_string)
                    elif db_type == "sqlserver":
                        schema_dict = analyze_sqlserver_schema(db_connection_string)
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
            elif db_type == 'sqlserver':
                schema_dict = analyze_sqlserver_schema(db_connection_string)
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
        
        # Log and ensure directories exist
        indexing_logger.info(f"[collection_add_docs_view] Collection: {collection_name}")
        indexing_logger.info(f"[collection_add_docs_view] Collections base path: {collections_path}")
        indexing_logger.info(f"[collection_add_docs_view] Collections path exists: {os.path.exists(collections_path)}")
        indexing_logger.info(f"[collection_add_docs_view] Collections path writable: {os.access(collections_path, os.W_OK)}")
        indexing_logger.info(f"[collection_add_docs_view] Collection path: {collection_path}")
        indexing_logger.info(f"[collection_add_docs_view] Docs path: {docs_path}")
        indexing_logger.info(f"[collection_add_docs_view] Collection exists in filesystem: {os.path.exists(collection_path)}")
        indexing_logger.info(f"[collection_add_docs_view] Docs folder exists: {os.path.exists(docs_path)}")
        
        # Ensure collection directory exists
        if not os.path.exists(collection_path):
            indexing_logger.warning(f"[collection_add_docs_view] Collection directory missing! Creating...")
            try:
                create_folder(collection_path)
                indexing_logger.info(f"[collection_add_docs_view] ✓ Collection directory created")
            except Exception as e:
                indexing_logger.error(f"[collection_add_docs_view] ✗ Failed to create collection directory: {e}")
                return JsonResponse({'error': f'Failed to create collection directory: {e}'}, status=500)
        
        # Ensure docs folder exists
        if not os.path.exists(docs_path):
            indexing_logger.warning(f"[collection_add_docs_view] Docs folder missing! Creating...")
            try:
                create_folder(docs_path)
                indexing_logger.info(f"[collection_add_docs_view] ✓ Docs folder created")
            except Exception as e:
                indexing_logger.error(f"[collection_add_docs_view] ✗ Failed to create docs folder: {e}")
                return JsonResponse({'error': f'Failed to create docs folder: {e}'}, status=500)
        
        index = index_builder(collection_path)
        create_all_docs_collection()
        all_docs_index = index_builder(all_docs_collection_path)
        
        # Initialize progress tracking in session
        total_files = len(uploaded_files)
        request.session['indexing_progress'] = {'current': 0, 'total': total_files, 'filename': ''}
        request.session.save()
        indexing_logger.info(f"\n{'='*60}\nStarting indexing: {total_files} files\n{'='*60}")
        
        for file_idx, file in enumerate(uploaded_files, 1):
            file_name = file.name
            # Update progress
            request.session['indexing_progress'] = {'current': file_idx, 'total': total_files, 'filename': file_name}
            request.session.save()
            
            # Minimal console output  
            doc_path = os.path.join(docs_path, file_name)
            doc_path = default_storage.get_available_name(doc_path)
            default_storage.save(doc_path, ContentFile(file.read()))

            # Load document with timeout protection
            indexing_logger.info(f"Processing file {file_idx}/{total_files}: {file_name}")
            try:
                document = load_document_with_timeout(doc_path, timeout_seconds=60)
            except TimeoutException as e:
                indexing_logger.warning(f"⚠ SKIPPED (timeout): {file_name}")
                continue
            except Exception as e:
                indexing_logger.error(f"✗ SKIPPED (error): {file_name} - {str(e)}")
                continue
            
            # Document loaded successfully, now index it
            try:
                indexing_logger.info(f"   Creating document object and indexing...")
                doc_sha256 = hash_file(doc_path)["sha256"]

                doc_obj = Document.objects.create(user=user, name=file_name, public=False,
                                                  description=None, loc=doc_path, sha256=doc_sha256)
                indexing_logger.info(f"   ✓ Document object created (ID: {doc_obj.id})")
                
                # Create indexes - FIX: Batch insertions and separate index operations to avoid SQLite contention on Linux
                indexing_logger.info(f"   Preparing {len(document)} chunks for indexing...")
                indexing_logger.info(f"   Index object: {index}")
                indexing_logger.info(f"   All_docs_index object: {all_docs_index}")
                
                # Create all LlamaIndex documents first
                docs_to_index = []
                for idx_chunk, chunked_doc in enumerate(document):
                    doc = llama_index_doc(text=chunked_doc.text, id_=f"{doc_obj.id}_{idx_chunk}")
                    docs_to_index.append(doc)
                indexing_logger.info(f"   ✓ Created {len(docs_to_index)} document objects")
                
                if doc_sha256 not in all_docs_collection_vdb.docs.values_list("sha256", flat=True):
                    # Insert all chunks into collection index first (batch operation with micro-batches for Linux)
                    indexing_logger.info(f"   Inserting {len(docs_to_index)} chunks into COLLECTION index...")
                    MICRO_BATCH_SIZE = 3  # Insert 3 chunks at a time to prevent resource exhaustion
                    for i in range(0, len(docs_to_index), MICRO_BATCH_SIZE):
                        batch_end = min(i + MICRO_BATCH_SIZE, len(docs_to_index))
                        indexing_logger.info(f"   Micro-batch {i//MICRO_BATCH_SIZE + 1}: chunks {i+1}-{batch_end}")
                        
                        for idx_chunk in range(i, batch_end):
                            doc = docs_to_index[idx_chunk]
                            indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] Collection insert...")
                            try:
                                index.insert(doc)
                                indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] ✓")
                            except Exception as e:
                                indexing_logger.error(f"      ✗ Collection insert failed: {e}")
                                raise
                        
                        # Force garbage collection and small pause after each micro-batch
                        if sys.platform.startswith('linux'):
                            gc.collect()
                            time.sleep(0.1)
                            indexing_logger.info(f"   Micro-batch complete, memory cleared")
                    
                    indexing_logger.info(f"   ✓ All chunks inserted into collection index")
                    
                    # Give ChromaDB/SQLite time to commit on Linux
                    if sys.platform.startswith('linux'):
                        indexing_logger.info(f"   [Linux] Pausing 1s for SQLite commit...")
                        time.sleep(1.0)
                        gc.collect()
                    
                    # Now insert all chunks into all_docs index (separate batch)
                    indexing_logger.info(f"   Inserting {len(docs_to_index)} chunks into ALL_DOCS index...")
                    for i in range(0, len(docs_to_index), MICRO_BATCH_SIZE):
                        batch_end = min(i + MICRO_BATCH_SIZE, len(docs_to_index))
                        indexing_logger.info(f"   Micro-batch {i//MICRO_BATCH_SIZE + 1}: chunks {i+1}-{batch_end}")
                        
                        for idx_chunk in range(i, batch_end):
                            doc = docs_to_index[idx_chunk]
                            indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] All_docs insert...")
                            try:
                                all_docs_index.insert(doc)
                                indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] ✓")
                            except Exception as e:
                                indexing_logger.error(f"      ✗ All_docs insert failed: {e}")
                                raise
                        
                        # Force garbage collection and small pause after each micro-batch
                        if sys.platform.startswith('linux'):
                            gc.collect()
                            time.sleep(0.1)
                            indexing_logger.info(f"   Micro-batch complete, memory cleared")
                    
                    indexing_logger.info(f"   ✓ All chunks inserted into all_docs index")
                    
                    # Force ChromaDB sync on Linux by querying count
                    if sys.platform.startswith('linux'):
                        indexing_logger.info(f"   [Linux] Ensuring ChromaDB sync...")
                        try:
                            if hasattr(index, '_chroma_collection'):
                                count = index._chroma_collection.count()
                                indexing_logger.info(f"   ✓ Collection has {count} vectors in ChromaDB")
                            if hasattr(all_docs_index, '_chroma_collection'):
                                all_count = all_docs_index._chroma_collection.count()
                                indexing_logger.info(f"   ✓ All_docs has {all_count} vectors in ChromaDB")
                            time.sleep(0.5)  # Give filesystem time to sync
                        except Exception as e:
                            indexing_logger.warning(f"   ⚠ ChromaDB sync check failed: {e}")
                    
                    all_docs_collection_vdb.docs.add(doc_obj)
                    collection_vdb.docs.add(doc_obj)
                    indexing_logger.info(f"   ✓ Indexed to collection and all_docs")
                else:
                    # Only insert into collection index
                    indexing_logger.info(f"   Document already in all_docs, inserting {len(docs_to_index)} chunks into collection only...")
                    MICRO_BATCH_SIZE = 3
                    for i in range(0, len(docs_to_index), MICRO_BATCH_SIZE):
                        batch_end = min(i + MICRO_BATCH_SIZE, len(docs_to_index))
                        indexing_logger.info(f"   Micro-batch {i//MICRO_BATCH_SIZE + 1}: chunks {i+1}-{batch_end}")
                        
                        for idx_chunk in range(i, batch_end):
                            doc = docs_to_index[idx_chunk]
                            indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] Collection insert...")
                            try:
                                index.insert(doc)
                                indexing_logger.info(f"      [{idx_chunk+1}/{len(docs_to_index)}] ✓")
                            except Exception as e:
                                indexing_logger.error(f"      ✗ Insert failed: {e}")
                                raise
                        
                        # Force garbage collection and small pause after each micro-batch
                        if sys.platform.startswith('linux'):
                            gc.collect()
                            time.sleep(0.1)
                            indexing_logger.info(f"   Micro-batch complete, memory cleared")
                    
                    indexing_logger.info(f"   ✓ All chunks inserted into collection")
                    
                    # Force ChromaDB sync on Linux by querying count
                    if sys.platform.startswith('linux'):
                        indexing_logger.info(f"   [Linux] Ensuring ChromaDB sync...")
                        try:
                            if hasattr(index, '_chroma_collection'):
                                count = index._chroma_collection.count()
                                indexing_logger.info(f"   ✓ Collection has {count} vectors in ChromaDB")
                            time.sleep(0.5)  # Give filesystem time to sync
                        except Exception as e:
                            indexing_logger.warning(f"   ⚠ ChromaDB sync check failed: {e}")
                    
                    collection_vdb.docs.add(doc_obj)
                    indexing_logger.info(f"   ✓ Indexed to collection")
                
                # Verify document was added
                doc_count = collection_vdb.docs.count()
                indexing_logger.info(f"   Collection now has {doc_count} documents")
                
                # FINAL VERIFICATION: Check SQLite database
                final_sqlite_check = os.path.join(collection_path, "chroma.sqlite3")
                if os.path.exists(final_sqlite_check):
                    size_kb = os.path.getsize(final_sqlite_check) / 1024
                    indexing_logger.info(f"   ✓ FINAL CHECK: SQLite DB = {size_kb:.2f} KB")
                    indexing_logger.info(f"   ✓ Collection path for querying: {collection_path}")
                    indexing_logger.info(f"   ✓ Collection DB entry loc: {collection_vdb.loc}")
                else:
                    indexing_logger.error(f"   ✗ FINAL CHECK: SQLite DB MISSING!")
                    indexing_logger.error(f"   Collection path: {collection_path}")
                    indexing_logger.error(f"   Directory contents: {os.listdir(collection_path) if os.path.exists(collection_path) else 'DIR NOT FOUND'}")
                
                
                # FINAL VERIFICATION: Check SQLite database
                final_sqlite_check = os.path.join(collection_path, "chroma.sqlite3")
                if os.path.exists(final_sqlite_check):
                    size_kb = os.path.getsize(final_sqlite_check) / 1024
                    indexing_logger.info(f"   ✓ FINAL CHECK: SQLite DB = {size_kb:.2f} KB")
                    indexing_logger.info(f"   ✓ Collection path for querying: {collection_path}")
                    indexing_logger.info(f"   ✓ Collection DB entry loc: {collection_vdb.loc}")
                else:
                    indexing_logger.error(f"   ✗ FINAL CHECK: SQLite DB MISSING!")
                    indexing_logger.error(f"   Collection path: {collection_path}")
                    indexing_logger.error(f"   Directory contents: {os.listdir(collection_path) if os.path.exists(collection_path) else 'DIR NOT FOUND'}")
                
                indexing_logger.info(f"✓ COMPLETED: {file_name}")
                
            except Exception as e:
                indexing_logger.error(f"✗ INDEXING FAILED for {file_name}: {str(e)}")
                import traceback
                indexing_logger.error(traceback.format_exc())
                # Delete the file if indexing failed
                if os.path.exists(doc_path):
                    os.remove(doc_path)
                continue
        
        # Clear progress after completion
        request.session['indexing_progress'] = None
        request.session.save()
        indexing_logger.info(f"\n{'='*60}\n✓ INDEXING COMPLETED\n{'='*60}\n")

        return redirect('main:collection', collection_id=collection_id)


# User Management Views
def is_admin_or_superuser(user):
    return user.is_superuser or user.groups.filter(name='Admin').exists()


@login_required(login_url='users:login')
@user_passes_test(is_admin_or_superuser, login_url='main:main_chat')
def users_list(request):
    """Display all users with search functionality"""
    search_query = request.GET.get('search', '')
    
    if search_query:
        users = User.objects.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        ).order_by('username')
    else:
        users = User.objects.all().order_by('username')
    
    groups = Group.objects.all()
    
    context = {
        'users': users,
        'groups': groups,
        'search_query': search_query,
    }
    return render(request, 'main/users_list.html', context)


@login_required(login_url='users:login')
@user_passes_test(is_admin_or_superuser, login_url='main:main_chat')
def user_create(request):
    """Create a new user"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        is_active = request.POST.get('is_active') == 'on'
        is_staff = request.POST.get('is_staff') == 'on'
        is_superuser = request.POST.get('is_superuser') == 'on'
        group_ids = request.POST.getlist('groups')
        
        # Validate required fields
        if not username or not password:
            return redirect('main:users_list')
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
            is_staff=is_staff,
            is_superuser=is_superuser
        )
        
        # Add groups
        if group_ids:
            groups = Group.objects.filter(id__in=group_ids)
            user.groups.set(groups)
        
        # Automatically add superusers to Admin group
        if is_superuser:
            admin_group, _ = Group.objects.get_or_create(name='Admin')
            user.groups.add(admin_group)
        
        return redirect('main:users_list')
    
    return redirect('main:users_list')


@login_required(login_url='users:login')
@user_passes_test(is_admin_or_superuser, login_url='main:main_chat')
def user_edit(request, username):
    """Edit an existing user"""
    if request.method == 'POST':
        try:
            user = User.objects.get(username=username)
            
            # Update basic fields
            new_username = request.POST.get('username', user.username)
            # Only update username if it changed and doesn't conflict
            if new_username != user.username:
                user.username = new_username
            user.email = request.POST.get('email', user.email)
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.is_active = request.POST.get('is_active') == 'on'
            user.is_staff = request.POST.get('is_staff') == 'on'
            user.is_superuser = request.POST.get('is_superuser') == 'on'
            
            # Update password if provided
            password = request.POST.get('password')
            if password:
                user.set_password(password)
            
            # Update groups
            group_ids = request.POST.getlist('groups')
            if group_ids:
                groups = Group.objects.filter(id__in=group_ids)
                user.groups.set(groups)
            else:
                user.groups.clear()
            
            # Automatically add Admin group if user is superuser (but allow manual removal)
            admin_group, _ = Group.objects.get_or_create(name='Admin')
            if user.is_superuser and admin_group not in user.groups.all():
                user.groups.add(admin_group)
            
            user.save()
        except User.DoesNotExist:
            pass
    
    return redirect('main:users_list')


@login_required(login_url='users:login')
@user_passes_test(is_admin_or_superuser, login_url='main:main_chat')
def user_delete(request, username):
    """Delete a user"""
    if request.method == 'POST':
        try:
            user = User.objects.get(username=username)
            # Prevent deleting yourself
            if user.username != request.user.username:
                user.delete()
        except User.DoesNotExist:
            pass
    
    return redirect('main:users_list')