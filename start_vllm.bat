@echo off
wsl -e bash -ic "cd ~ && source vllm-venv/bin/activate && python -m vllm.entrypoints.openai.api_server --host 0.0.0.0 --port 8002 --model /home/farshad/models/Qwen3-4B-AWQ --served-model-name Qwen3-4B --dtype auto --quantization awq --max-model-len 16384 --gpu-memory-utilization 0.80 --enforce-eager --swap-space 1; exec bash"
