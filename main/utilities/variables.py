from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
from llama_index.prompts.prompts import SimpleInputPrompt
import accelerate
import torch
import time
from pprint import pprint


model_name = "TheBloke/Mistral-7B-Instruct-v0.2-GPTQ"


INDEXING_CHUNK_SIZE = 384
INDEXING_CHUNK_OVERLAP = 64


if "llama" in model_name.lower():
    model_type = 'llama'
elif "mistral" in model_name.lower():
    model_type ='mistral'

# setting device
gpu=0
device = torch.device(f"cuda:{gpu}" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.cuda.set_device(device)
torch.cuda.get_device_name(0)




# Llama2
system_prompt_llama = """<s>[INST] <<SYS>>
You are a helpful, respectful and honest assistant. Always answer as
helpfully as possible, while being safe.
If a question does not make any sense, or is not factually coherent, explain
why instead of answering something not correct. If you don't know the answer
to a question, please express that you do not have informaion or knowledge in that context and please don't share false information.
Try to be exact in information and numbers you tell.
Your goal is to provide answers based on the information provided and your other knowledge.<</SYS>>
"""

query_wrapper_prompt_llama = SimpleInputPrompt("{query_str} [/INST]")


# Mistral
system_prompt_mistral = """<|im_start|>system
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

User: What are the effects of climate change on polar bear populations? explain breifly.
Keywords: climate change, polar bears, effects

User: How does the Transformer architecture work in deep learning?
Keywords: Transformer, deep learning, architecture

User: سلام، بگو ببینم حافظه کاری در روانشناسی چی هست؟
Keywords: حافظه کاری, روانشناسی

Now extract keywords from the following query:
"""

system_prompt = """ You are a helpful RAG assistant. Use the retrieved context to answer the user’s question.  
If the context is enough, answer directly.  
If you add your own knowledge or analysis, make this clear (e.g., “based on the retrieved texts…” or “my additional analysis is…”).  
Be concise, clear, and helpful."""