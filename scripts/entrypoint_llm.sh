#!/bin/sh

# Простая эвристика по имени образа для выбора аргументов
if echo "$LLM_ENGINE_IMAGE" | grep -q "sglang"; then
    echo "Starting SGLang for ${MODEL_NAME}..."
    exec python3 -m sglang.launch_server \
        --log-level debug \
        --model-path ${MODEL_NAME} \
        --mem-fraction-static ${GPU_MEM_FRACTION} \
        --tool-call-parser ${TOOL_CALL_PARSER} \
        --max-prefill-tokens 4096 \
        --served-model-name default-model \
        --quantization ${QUANTIZATION} \
        --host 0.0.0.0 \
        --port 8000 \
        --tp 1 \
        --max-prefill-tokens ${MAX_PREFILL_TOKENS} \
        --context-length ${CONTEXT_SIZE}
else
    echo "Starting vLLM for ${MODEL_NAME}..."
    # Ключевые изменения для Qwen 2.5
    exec python3 -m vllm.entrypoints.openai.api_server \
        --model ${MODEL_NAME} \
        --quantization ${QUANTIZATION} \
        --gpu-memory-utilization ${GPU_MEM_FRACTION} \
        --host 0.0.0.0 --port 8000 \
        --tool-call-parser hermes \
        --enable-auto-tool-choice \
        --served-model-name qwen-coder \
        --max-model-len ${CONTEXT_SIZE}
fi
#        --chat-template llama-3 \
#        --chat-template /app/qwen_tool_template.jinja \

#        --quantization ${QUANTIZATION} \
