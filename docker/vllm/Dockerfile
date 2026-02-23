FROM vllm/vllm-openai:v0.12.0

ENV PORT=8000
# No need to change MODEL_NAME here, can be overridden in cloud run deployment
ENV MODEL_NAME=google/gemma-3-12b-it
ENV VLLM_ARGS=""

EXPOSE 8000

# We use shell form for ENTRYPOINT to allow variable expansion for VLLM_ARGS
ENTRYPOINT python3 -m vllm.entrypoints.openai.api_server \
    --port ${PORT} \
    --model ${MODEL_NAME} \
    --gpu-memory-utilization 0.90 \
    --max-num-seqs 256 \
    --max-model-len 4096 \
    ${VLLM_ARGS}