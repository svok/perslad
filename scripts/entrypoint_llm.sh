#!/bin/sh

# Простая эвристика по имени образа для выбора аргументов
if echo "$LLM_ENGINE_IMAGE" | grep -q "sglang"; then
    echo "Starting SGLang for ${MODEL_NAME}..."
    exec python3 -m sglang.launch_server \
        --log-level info \
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
    exec python3 -m vllm.entrypoints.openai.api_server \
        --model ${MODEL_NAME} \
        --kv-cache-dtype fp8 \
        --host 0.0.0.0 --port 8000 \
        --no-enable-log-requests \
        --gpu-memory-utilization 0.85 \
        --max-num-seqs 2 \
        --max-num-batched-tokens 4096 \
        --block-size 16 --enforce-eager \
        --served-model-name default-model \
        --enable-auto-tool-choice \
        --tool-call-parser ${TOOL_CALL_PARSER} \
        --max-model-len ${CONTEXT_SIZE}
fi

#        --quantization ${QUANTIZATION} \
#        --enable-lora \
#        --max-loras 6 \
#        --max-lora-rank 32 \
#        --tool-call-parser ${TOOL_CALL_PARSER} \
#        --enable-auto-tool-choice \
