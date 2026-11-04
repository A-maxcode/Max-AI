# Local GGUF model

Max-AI uses an existing open-weight model; it does not train a foundation
model. The included Compose service runs the CPU-capable llama.cpp server and
loads a GGUF file from `model/weights/`. Model files are intentionally excluded
from Git and are never downloaded by the application at startup.

## Select a model

The starter configuration uses **Qwen2.5-3B-Instruct GGUF**, an existing
instruction-tuned model published by Qwen
([model card and files](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF)).
Its Q4_K_M quantization is a reasonable CPU-oriented starting point for
personal testing. The linked GGUF repository includes a Qwen Research License
Agreement; do not assume Apache 2.0 applies to this artifact. Review the
exact model card and terms before use. Before using any model:

1. Read the model card and verify the publisher, architecture, GGUF file, and
   exact license for the artifact you download.
2. Confirm that your intended use complies with its license and any applicable
   acceptable-use terms. "Open weight" does not mean public domain or
   unrestricted use.
3. Check storage and RAM/VRAM requirements for the chosen quantization,
   context length, and expected concurrent users. A 3B Q4 model file is around
   2 GB; plan for additional memory for the runtime, KV cache, OS, and other
   services. 8 GB or more system RAM is a practical minimum for a small CPU
   test deployment, not a performance guarantee.
4. For GPU acceleration, use a llama.cpp image built for your hardware and
   configure GPU passthrough explicitly. The default `server` image runs on
   CPU; no GPU is assumed.

## Download a model manually

Install the Hugging Face CLI separately if needed, review the model card, and
download only the GGUF file you selected:

```sh
hf download Qwen/Qwen2.5-3B-Instruct-GGUF \
  qwen2.5-3b-instruct-q4_k_m.gguf \
  --local-dir model/weights
```

Set `MODEL_FILE` in the root `.env` to the downloaded filename. Use a different
repository and filename only after verifying that the model is compatible with
llama.cpp and its license. Keep weights in `model/weights/`; that directory is
git-ignored and is mounted read-only into the inference container.

## Runtime configuration

`MODEL_CONTEXT_LENGTH`, `MODEL_MAX_TOKENS`, and `MODEL_GPU_LAYERS` configure
llama.cpp at container startup. `MODEL_SERVER_URL` points the backend at the
private Compose service. The model server port is bound to `127.0.0.1` for
host-based development and is not exposed on public interfaces; in Compose,
the backend reaches it over the private service network.
