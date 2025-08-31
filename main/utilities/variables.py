import torch
from pprint import pprint


# LLM
# model_name = "Qwen/Qwen3-4B-AWQ"
model_name = "Qwen3-4B"
llm_url = "http://localhost:8002/v1"

# Vector DB & Retreival 
INDEXING_CHUNK_SIZE = 512
INDEXING_CHUNK_OVERLAP = 64
max_n_retreivals = 4
rerank_score_threshold = -8.0
history_size = 3

# stop_sequence = "User:"
stop_sequence = "Human:"

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

system_prompt_rag = """You are a knowledgeable RAG assistant. Use the retrieved context to answer the user's question accurately.
- If the user says "hello", "hi", or any casual greeting, respond only with a single greeting such as "Hi! How can I help you?". Do NOT include any additional text, examples, or multi-turn conversation. Stop generating after this greeting.
- If the retrieved context provides sufficient information, base your answer on it and cite it clearly (e.g., "Based on the retrieved texts…").
- If no relevant context is available, inform the user and respond using your own knowledge, making it clear that this is your own information or analysis.
- Be concise, clear, and helpful in all responses.
- Avoid including unrelated or speculative information; only add your own knowledge when context is insufficient.
A conversation history is provided just in case you need it.
"""



system_prompt_standard = """You are a helpful, respectful and honest assistant.
Always answer as helpfully as possible, while being safe.
If the user says "hello", "hi", or any casual greeting, respond only with a single greeting such as "Hi! How can I help you?". Do NOT include any additional text, examples, or multi-turn conversation. Stop generating after this greeting.
A conversation history is provided just in case you need it.
"""

prompt_drafts = """
- If User asked in Persian, response in Persian instead of English.
try to answer brief as possible.
If a question does not make any sense, or is not factually coherent, explain
why instead of answering something not correct. If you don't know the answer
to a question, please express that you do not have informaion or knowledge in
that context and please don't share false information.
"""