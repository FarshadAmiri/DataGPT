@echo off
wsl -e bash -ic "cd ~ && source vllm-venv/bin/activate && python -m vllm.entrypoints.openai.api_server \
--host 0.0.0.0 --port 8002 \
--model Qwen/Qwen3-4B-AWQ \
--dtype auto \
--quantization awq \
--max-model-len 2048 \
--gpu-memory-utilization 0.80 \
--enforce-eager \
--swap-space 2"
pause
