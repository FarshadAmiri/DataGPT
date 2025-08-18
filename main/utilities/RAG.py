from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer, AutoModelForSequenceClassification
from sentence_transformers import CrossEncoder
from huggingface_hub import login
from llama_index.embeddings.langchain import LangchainEmbedding
from langchain_huggingface import HuggingFaceEmbeddings
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from main.models import Thread, Document
import chromadb
from pathlib import Path
import accelerate
import torch
import os
from pprint import pprint
from main.models import Collection
from users.models import User
from main.utilities.variables import INDEXING_CHUNK_SIZE, INDEXING_CHUNK_OVERLAP
from typing import List, Tuple, Optional, Union


# ------- NameSpaces -------
all_docs_collection_name = "ALL_DOCS_COLLECTION"
all_docs_collection_path = os.path.join("collections", all_docs_collection_name)


embedding_model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
embedding_model_lc = LangchainEmbedding(HuggingFaceEmbeddings(model_name=embedding_model_name))
embedding_model_st = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
embedding_model_st2 = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="paraphrase-multilingual-MiniLM-L12-v2")


# Load model & tokenizer once (outside the function for efficiency)
reranker_name = "Alibaba-NLP/gte-multilingual-reranker-base"
tokenizer = AutoTokenizer.from_pretrained(reranker_name)
reranker = AutoModelForSequenceClassification.from_pretrained(
    reranker_name, trust_remote_code=True, torch_dtype=torch.float16
)
reranker.eval()

# Load MiniLM CrossEncoder once (fast to reuse)
minilm_reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

# ------- END of NameSpaces -------

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

    with open('huggingface_credentials.txt', 'r') as file:
        hf_token = file.readline().strip()

    login(token=hf_token)

    # Create tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name
        ,device_map='cuda'                 
        )

    # Define model
    model = AutoModelForCausalLM.from_pretrained(model_name
        # ,cache_dir=r"C:\Users\henry\.cache\huggingface\hub"
        ,device_map='cuda'  
        # , torch_dtype=torch.float16
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
    exist = Collection.objects.filter(name=all_docs_collection_name).exists() and os.path.exists(all_docs_collection_path)
    if not exist:
        db = chromadb.PersistentClient(path=all_docs_collection_path)
        chroma_collection = db.get_or_create_collection("default", embedding_function=embedding_model_st2)
        all_docs_creator = User.objects.filter(username="admin").first()
        if all_docs_creator == None:
            all_docs_creator = User.objects.filter(groups__name='Admin').first()
        Collection.objects.create(name=all_docs_collection_name, user_created=all_docs_creator, loc=all_docs_collection_path)
    return



def index_builder(vdb_path: str):
    from llama_index.core import Settings
    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.llms.huggingface import HuggingFaceLLM
    from llama_index.vector_stores.chroma import ChromaVectorStore
    import chromadb
    from main.views import model, tokenizer
    
    # Define your LLM
    llm = HuggingFaceLLM(
        model=model,
        tokenizer=tokenizer,
        context_window=4096,
    )

    # Configure global settings (instead of ServiceContext)
    Settings.llm = llm
    Settings.chunk_size = INDEXING_CHUNK_SIZE
    Settings.chunk_overlap = INDEXING_CHUNK_OVERLAP
    Settings.embed_model = embedding_model_lc

    # Setup Chroma
    db = chromadb.PersistentClient(path=vdb_path)
    chroma_collection = db.get_or_create_collection(
        "default",
        # embedding_function=embedding_model_st2
    )
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Build index (no more service_context param)
    index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )

    return index


def rerank_alibaba(query: str, texts: List[str], threshold: Optional[float] = None, return_scores: bool = False) -> Union[List[str], Tuple[List[str], List[float]]]:
    """
    Reranks a list of texts based on relevance to a query using the multilingual reranker.

    Args:
        query (str): The search query.
        texts (List[str]): List of candidate passages.
        threshold (float, optional): Minimum score to include a passage.
        return_scores (bool): Whether to return scores alongside ranked texts.

    Returns:
        Either:
            - List of ranked texts (if return_scores=False)
            - Tuple[List[str], List[float]] (if return_scores=True)
    """
    pairs = [(query, doc) for doc in texts]

    with torch.no_grad():
        inputs = tokenizer(
            pairs, padding=True, truncation=True, return_tensors='pt', max_length=512
        )
        scores = reranker(**inputs, return_dict=True).logits.view(-1).float().tolist()

    # Zip texts and scores, sort by score descending
    ranked = sorted(zip(texts, scores), key=lambda x: x[1], reverse=True)

    # Apply threshold filter if specified
    if threshold is not None:
        ranked = [(t, s) for t, s in ranked if s >= threshold]

    ranked_texts = [t for t, _ in ranked]
    ranked_scores = [s for _, s in ranked]

    return (ranked_texts, ranked_scores) if return_scores else ranked_texts



def rerank_minilm(query: str, texts: List[str], threshold: Optional[float] = None, return_scores: bool = False) -> Union[List[str], Tuple[List[str], List[float]]]:
    """
    Reranks a list of texts based on relevance to a query using MiniLM CrossEncoder.

    Args:
        query (str): The search query.
        texts (List[str]): List of candidate passages.
        threshold (float, optional): Minimum score to include a passage.
        return_scores (bool): Whether to return scores alongside ranked texts.

    Returns:
        Either:
            - List of ranked texts (if return_scores=False)
            - Tuple[List[str], List[float]] (if return_scores=True)
    """
    # Prepare (query, passage) pairs
    pairs = [(query, doc) for doc in texts]

    # Get relevance scores
    scores = minilm_reranker.predict(pairs).tolist()

    # Zip texts with scores and sort
    ranked = sorted(zip(texts, scores), key=lambda x: x[1], reverse=True)

    # Apply threshold filter if specified
    if threshold is not None:
        ranked = [(t, s) for t, s in ranked if s >= threshold]

    ranked_texts = [t for t, _ in ranked]
    ranked_scores = [s for _, s in ranked]

    return (ranked_texts, ranked_scores) if return_scores else ranked_texts
