from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
from huggingface_hub import login
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
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
import chromadb
from pathlib import Path
import torch


INDEXING_CHUNK_SIZE = 384
INDEXING_CHUNK_OVERLAP = 64


model_name = "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ"
embedding_model = LangchainEmbedding(HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"))
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="paraphrase-multilingual-MiniLM-L12-v2")

# Mistral
system_prompt = """<|im_start|>system
You are a helpful, respectful and honest assistant.
Always answer as helpfully as possible, while being safe.
If a question does not make any sense, or is not factually coherent, explain
why instead of answering something not correct. If you don't know the answer
to a question, please express that you do not have informaion or knowledge in
that context and please don't share false information.
Try to be exact in information and numbers you tell.
Your goal is to provide answers based on the information provided, so do not
use your prior knowledge.<|im_end|>
<|im_start|>user
"""

# ----- keyword_extractor_prompt -----
keyword_extractor_prompt = """You are a smart AI assistant helping with document retrieval.
Your job is to extract only the essential keywords and phrases from a user query that can be used to retrieve relevant documents. Do NOT rewrite the query. Instead, return a minimal list of distinct, meaningful terms or short phrases.
Do not include stopwords, pronouns, greetings, or irrelevant words. Focus on entities, topics, key terms, technical concepts, and specific content.
Return keywords as a comma-separated list, and nothing else.

Examples:

User: What are the effects of climate change on polar bear populations?
Keywords: climate change, polar bears, effects

User: How does the Transformer architecture work in deep learning?
Keywords: Transformer, deep learning, architecture

User: سلام، بگو ببینم حافظه کاری در روانشناسی چی هست؟
Keywords: حافظه کاری, روانشناسی

Now extract keywords from the following query:
"""


query_wrapper_prompt = SimpleInputPrompt("""{query_str} <|im_end|>
<|im_start|>assistant
""")


def load_model(model_name, device='gpu'):
    if device == 'gpu':
        gpu=0
        device = torch.device(f"cuda:{gpu}" if torch.cuda.is_available() else "cpu")
        if torch.cuda.is_available():
            torch.cuda.set_device(device)
        torch.cuda.get_device_name(0)
    elif device == 'cpu':
        device = torch.device('cpu')
        torch.cuda.set_device(device)

    with open('D:\Projects\RAG-webapp\huggingface_credentials.txt', 'r') as file:
        hf_token = file.readline().strip()

    login(token=hf_token)

    # Create tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name,device_map='cuda')
    model = AutoModelForCausalLM.from_pretrained(model_name,device_map='cuda').to(device)
    streamer = TextStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    model_obj = {"model": model, "tokenizer": tokenizer, "streamer": streamer, "device": device,  }

    return model_obj


model_obj = load_model(model_name)
model = model_obj["model"]
tokenizer = model_obj["tokenizer"]
device = model_obj["device"]
streamer = model_obj["streamer"]


def create_rag(path):
    db = chromadb.PersistentClient(path=path)
    chroma_collection = db.get_or_create_collection("default")
    return


def add_docs(vdb_path: str, docs_paths: list):
    db = chromadb.PersistentClient(path = vdb_path)
    chroma_collection = db.get_or_create_collection("default", embedding_function=sentence_transformer_ef)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    llm = HuggingFaceLLM(context_window=4096,
                     max_new_tokens=512,
                     system_prompt=system_prompt,
                     query_wrapper_prompt=query_wrapper_prompt,
                     model=model,
                     tokenizer=tokenizer)

    # Create new service context instance
    service_context = ServiceContext.from_defaults(
        chunk_size=INDEXING_CHUNK_SIZE,
        chunk_overlap=INDEXING_CHUNK_OVERLAP,
        llm=llm,
        embed_model=embedding_model
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
        llm = HuggingFaceLLM(context_window=4096,
                    max_new_tokens=512,
                    system_prompt=system_prompt,
                    query_wrapper_prompt=query_wrapper_prompt,
                    model=model,
                    tokenizer=tokenizer)

        # Create new service context instance
        service_context = ServiceContext.from_defaults(
            chunk_size=INDEXING_CHUNK_SIZE,
            chunk_overlap=INDEXING_CHUNK_OVERLAP,
            llm=llm,
            embed_model=embedding_model
        )

        # And set the service context
        set_global_service_context(service_context)
        
        db = chromadb.PersistentClient(path = vdb_path)
        chroma_collection = db.get_or_create_collection("default", embedding_function=sentence_transformer_ef)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)
    except:
        llm = HuggingFaceLLM(context_window=4096,
                    max_new_tokens=512,
                    system_prompt=system_prompt,
                    query_wrapper_prompt=query_wrapper_prompt,
                    model=model,
                    tokenizer=tokenizer)

        # Create new service context instance
        service_context = ServiceContext.from_defaults(
            chunk_size=INDEXING_CHUNK_SIZE,
            chunk_overlap=INDEXING_CHUNK_OVERLAP,
            llm=llm,
            embed_model=embedding_model
        )

        # And set the service context
        set_global_service_context(service_context)

        db = chromadb.PersistentClient(path = vdb_path)
        chroma_collection = db.get_or_create_collection("default", embedding_function=sentence_transformer_ef)
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context)

    return index





""" ---------------- Helper functions ---------------- """


import os, shutil
import hashlib
import re


def create_folder(path):
    existed = True
    if not os.path.exists(path):
        os.makedirs(path)
        existed = False
    return existed


def get_first_words(text, character_limitation=60):
    if len(text) <= character_limitation:
        return text
    else:
        space_index = text.rfind(' ', 0, character_limitation)
        if space_index != -1:
            return text[:space_index]
        else:
            return text[:character_limitation]
        

def get_folder_names(directory_path):
    folder_names = []
    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)
        if os.path.isdir(item_path):
            folder_names.append(item)
    return folder_names


def copy_folder_contents(source, destination, exclude_folder):
    for item in os.listdir(source):
        source_path = os.path.join(source, item)
        destination_path = os.path.join(destination, item)
        if item != exclude_folder:
            if os.path.isdir(source_path):
                shutil.copytree(source_path, destination_path)
            else:
                shutil.copy2(source_path, destination_path)


def hash_file(file_path):
    # BUF_SIZE is totally arbitrary, change for your app!
    BUF_SIZE = 65536  # lets read stuff in 64kb chunks!

    hashes = dict()
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()

    with open(file_path, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            md5.update(data)
            sha256.update(data)
            
    hashes["md5"] = md5.hexdigest()
    hashes["sha256"] = sha256.hexdigest()
    
    return hashes


def remove_non_printable(text):
    pattern = r'[\x00-\x1F\x7F-\xFF]'
    cleaned_text = re.sub(pattern, '', text)
    return cleaned_text