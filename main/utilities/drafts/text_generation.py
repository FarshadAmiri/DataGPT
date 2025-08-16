from transformers import AutoTokenizer, AutoModelForCausalLM, TextStreamer
import accelerate
import torch
import time
from pprint import pprint


def llm_inference(plain_text, max_length=4000, ):
    from .variables import device, model, tokenizer, streamer

    input_ids = tokenizer.encode(
        plain_text,
        return_tensors="pt",
        truncation=True,
        max_length=max_length,
        ).to(device)
    
    output_ids = model.generate(input_ids
                        ,streamer=streamer
                        ,use_cache=True
                        ,max_new_tokens=float('inf')
                       )
    answer = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0]
    return answer
