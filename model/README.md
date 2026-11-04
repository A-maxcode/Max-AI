# Local GGUF model

Max-AI runs the existing **SmolLM2 1.7B Instruct** model through the official
CPU-capable llama.cpp server image. This is a downloaded open-weight model, not
a foundation model trained by Max-AI.

## Selected model

- Publisher: Hugging FaceTB
- GGUF repository: [`HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF`](https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF)
- File: `smollm2-1.7b-instruct-q4_k_m.gguf`
- Quantization: Q4_K_M
- Download size: about 1.06 GB
- Repository license metadata: Apache-2.0

Review the model card and license before changing the model or using it for a
different purpose. The current model is suitable for a small CPU test server;
quality and speed are limited compared with larger models. This Codespace has
2 CPU cores and an 8 GiB Docker memory limit. The configuration uses a 2048
token context, two CPU threads, a single inference slot, and small batches to
fit that environment.

## Model storage

The model file is stored at:

```text
model/weights/smollm2-1.7b-instruct-q4_k_m.gguf
```

Compose bind-mounts `model/weights/` read-only at `/models` inside llama.cpp.
The host directory persists when containers are recreated and is ignored by
Git, so the model binary is not included in commits or Docker build context.
To download it again:

```sh
curl --fail --location --retry 3 \
  --output model/weights/smollm2-1.7b-instruct-q4_k_m.gguf \
  https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF/resolve/main/smollm2-1.7b-instruct-q4_k_m.gguf
```

Set `MODEL_PATH` in `.env` to the matching container path (default:
`/models/smollm2-1.7b-instruct-q4_k_m.gguf`). `MODEL_CONTEXT_LENGTH`,
`MODEL_MAX_TOKENS`, `MODEL_THREADS`, `MODEL_BATCH_SIZE`, and
`MODEL_GPU_LAYERS` tune the llama.cpp CPU server. The backend uses
`MODEL_SERVER_URL=http://model-server:8080` over a private Docker network; the
model server has no published host port.
