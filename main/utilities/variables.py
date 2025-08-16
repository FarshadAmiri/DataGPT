from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
from llama_index.prompts.prompts import SimpleInputPrompt
import accelerate
import torch
import time
from pprint import pprint


model_name = "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ"


INDEXING_CHUNK_SIZE = 384
INDEXING_CHUNK_OVERLAP = 64

max_n_retreivals = 8 
max_new_tokens = 1400
max_length = 18000


# setting device
gpu=0
device = torch.device(f"cuda:{gpu}" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.cuda.set_device(device)
torch.cuda.get_device_name(0)


# ----- keyword_extractor_prompt -----
keyword_extractor_prompt = """You are a smart AI assistant helping with document retrieval.
Your job is to extract ONLY the essential content-bearing keywords and phrases from a user query.
These keywords must be useful for vector database search.

Important rules:
- Include only nouns, proper nouns, entities, domain-specific terms, and technical concepts.
- Exclude generic verbs (e.g., explain, analyze, describe), adjectives, adverbs, stopwords, and pronouns.
- Do NOT include words like: what, how, effects, explain, impact, analysis, describe, definition, etc.
- Focus on core topics, entities, and technical terms.
- Return a short, minimal list of distinct terms or phrases.
- Output must be strictly a comma-separated list, and nothing else.

Examples:

User: What are the effects of climate change on polar bear populations? explain briefly.
Keywords: climate change, polar bears

User: How does the Transformer architecture work in deep learning?
Keywords: Transformer, deep learning

User: Explain the effects of railroads in Britain.
Keywords: railroads, Britain

User: سلام، بگو ببینم حافظه کاری در روانشناسی چی هست؟
Keywords: حافظه کاری, روانشناسی

Now extract keywords from the following query:
"""

# ----- Response Generation Prompts -----

system_prompt_rag = """ You are a helpful RAG assistant. Use the retrieved context to answer the user’s question.  
If the context is enough, answer directly.  
If you add your own knowledge or analysis, make this clear (e.g., “based on the retrieved texts…” or “my additional analysis is…”).  
Be concise, clear, and helpful.
If User asked in Persian, response in Persian instead of English.
"""


system_prompt_standard = """You are a helpful, respectful and honest assistant.
Always answer as helpfully as possible, while being safe.
If a question does not make any sense, or is not factually coherent, explain
why instead of answering something not correct. If you don't know the answer
to a question, please express that you do not have informaion or knowledge in
that context and please don't share false information.
If User asked in Persian, response in Persian instead of English.
try to answer brief as possible.
"""