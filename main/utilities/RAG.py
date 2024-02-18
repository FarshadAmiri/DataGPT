from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
from llama_index import VectorStoreIndex, SimpleDirectoryReader, get_response_synthesizer
from llama_index.vector_stores import ChromaVectorStore
from llama_index.storage.storage_context import StorageContext
from llama_index.prompts.prompts import SimpleInputPrompt
from llama_index.llms import HuggingFaceLLM
from llama_index.embeddings import LangchainEmbedding
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from llama_index import set_global_service_context
from llama_index import ServiceContext
from llama_index import VectorStoreIndex, download_loader
from llama_index import SimpleDirectoryReader
from llama_index.retrievers import VectorIndexRetriever
from llama_index.query_engine import RetrieverQueryEngine
from llama_index.postprocessor import SimilarityPostprocessor
from llama_index.vector_stores import MilvusVectorStore
from main.models import Thread, Document
import chromadb
from pathlib import Path
import accelerate
import torch
import time, os
from pprint import pprint
from main.models import Collection
from users.models import User


all_docs_collection_name = "ALL_DOCS_COLLECTION"
all_docs_collection_path = os.path.join("collections", all_docs_collection_name)


def load_model(model_name="TheBloke/Llama-2-7b-Chat-GPTQ", device='gpu'):
    # setting device
    if device == 'gpu':
        gpu=0
        device = torch.device(f"cuda:{gpu}" if torch.cuda.is_available() else "cpu")
        if torch.cuda.is_available():
            torch.cuda.set_device(device)
        torch.cuda.get_device_name(0)
    elif device == 'cpu':
        device = torch.device('cpu')
        torch.cuda.set_device(device)

    # Create tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name
        ,device_map='cuda'                 
        )

    # Define model
    model = AutoModelForCausalLM.from_pretrained(model_name
        ,cache_dir=r"C:\Users\henry\.cache\huggingface\hub"
        # ,cache_dir=r"C:\Users\user2\.cache\huggingface\hub"
        ,device_map='cuda'  
        # , torch_dtype=torch.float16
        # ,low_cpu_mem_usage=True
        # ,rope_scaling={"type": "dynamic", "factor": 2}
        # ,load_in_8bit=True,
        ).to(device)

    streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    model_obj = {"model": model, "tokenizer": tokenizer, "streamer": streamer, "device": device,  }
    return model_obj


def llm_inference(plain_text, model, tokenizer, device, streamer=None, max_length=4000, ):
    input_ids = tokenizer(
        plain_text,
        return_tensors="pt",
        truncation=True,
        max_length=max_length,
        )['input_ids'].to(device)
    
    output_ids = model.generate(input_ids
                        ,streamer=streamer
                        ,use_cache=True
                        ,max_new_tokens=float('inf')
                       )
    answer = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0]
    return answer


def create_rag(path):
    db = chromadb.PersistentClient(path=path)
    chroma_collection = db.get_or_create_collection("default")
    return


def create_all_docs_collection():
    global all_docs_collection_path, all_docs_collection_name
    if not os.path.exists(all_docs_collection_path):
        db = chromadb.PersistentClient(path=all_docs_collection_path)
        chroma_collection = db.get_or_create_collection("default")
        all_docs_creator = User.objects.filter(username="admin").first()
        if all_docs_creator == None:
            all_docs_creator = User.objects.filter(groups__name='Admin').first()
        Collection.objects.create(name=all_docs_collection_name, user_created=all_docs_creator, loc=all_docs_collection_path)
    return


def add_docs(vdb_path: str, docs_paths: list):
    from main.utilities.variables import system_prompt, query_wrapper_prompt
    from main.views import model, tokenizer
    db = chromadb.PersistentClient(path = vdb_path)
    chroma_collection = db.get_or_create_collection("default")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
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
    PyMuPDFReader = download_loader("PyMuPDFReader")
    loader = PyMuPDFReader()
    # Load documents
    print(f"\ndocs_paths: {docs_paths}\n")
    for doc_path in docs_paths:
        document = loader.load(file_path=Path(doc_path), metadata=False)
        # Create indexes
        for doc in document:
            index.insert(doc)


def index_builder(vdb_path: str):
    try:
        db = chromadb.PersistentClient(path = vdb_path)
        chroma_collection = db.get_or_create_collection("default")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
    except:
        from main.utilities.variables import system_prompt, query_wrapper_prompt
        from main.views import model, tokenizer
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

        db = chromadb.PersistentClient(path = vdb_path)
        chroma_collection = db.get_or_create_collection("default")
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)

    return index


def add_docs2(vdb_path: str, vdb, docs_dict: dict):
    from main.utilities.variables import system_prompt, query_wrapper_prompt
    from main.views import model, tokenizer
    db = chromadb.PersistentClient(path = vdb_path)
    chroma_collection = db.get_or_create_collection("default")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
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
    PyMuPDFReader = download_loader("PyMuPDFReader")
    loader = PyMuPDFReader()
    # Adding documents to vector database
    for doc in docs_dict:
        user = doc["user"]
        public = doc["public"]
        description = doc["description"]
        loc = doc["loc"]
        document_obj = doc["doc_obj"]

        document = loader.load(file_path=Path(loc), metadata=False)

        # Create indexes
        for chunked_doc in document:
            index.insert(chunked_doc)
        vdb.docs.add(document_obj)