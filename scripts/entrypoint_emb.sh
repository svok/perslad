#!/bin/sh

# Простая эвристика по имени образа для выбора аргументов
#if echo "$LLM_ENGINE_IMAGE" | grep -q "sglang"; then
#    echo "Starting SGLang for ${EMB_MODEL_NAME}..."
#    exec python3 -m sglang.launch_server \
#        --log-level info \
#        --is-embedding \
#        --model-path ${EMB_MODEL_NAME} \
#        --mem-fraction-static 0.1 \
#        --context-length 8192 \
#        --served-model-name embed-model \
#        --host 0.0.0.0 \
#        --port 8001 \
#        --tp 1
#else
    echo "Starting vLLM for ${EMB_MODEL_NAME}..."
    # Ключевые изменения для Qwen 2.5
    exec python3 -m vllm.entrypoints.openai.api_server \
        --model ${EMB_MODEL_NAME} \
        --port 8001 \
        --convert embed \
        --gpu-memory-utilization 0.07 \
        --max-model-len 512 \
        --served-model-name embed-model
#fi
