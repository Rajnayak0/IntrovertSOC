# RECOMMENDED_MODELS.md — Local GGUF models for IntrovertSOC

IntrovertSOC runs any OpenAI-compatible llamafile/llama-server endpoint. The model you pick is
**your** choice — no downloads happen automatically, nothing is fetched at runtime. This page is
the curated shortlist: ten well-known open-weight models with official or community GGUF
quantizations, sorted **heaviest → lightest**. Set the file you choose under
**Model Settings → GGUF model file**, copy the launch command, done.

## Quantization in 20 seconds

| Quant | Quality | When |
|---|---|---|
| `Q4_K_M` | High, community default | **Pick this unless you know otherwise** — ~30% of FP16 size, ~1-3 MMLU-Pro points lost |
| `Q5_K_M` / `Q6_K` | Very high | You have ≥25% memory headroom over Q4 |
| `Q8_0` | Near-lossless | Benchmarking / lots of RAM to burn |
| `Q3_K_M` and below | Visible degradation | Only if Q4 doesn't fit at all |

Rules of thumb: `Q4_K_M` ≈ **0.6 GB per billion parameters** (plus ~1.5-2 GB for KV cache at
8-32k context). A bigger model at Q4 beats a smaller model at Q8 whenever both fit.

## Top 10 (sorted heaviest → lightest, sizes at Q4_K_M)

| # | Model | Params | ~Size | Min RAM/VRAM | Context | License | GGUF source (Hugging Face) |
|---|---|---|---|---|---|---|---|
| 1 | **Llama 4 Scout** (MoE, 17B active) | 109B total | ~55 GB | 64 GB+ | 10M (YaRN) | Llama 4 Community | `bartowski` mirror of `meta-llama/Llama-4-Scout-17B-16E-Instruct` |
| 2 | **Qwen3-72B** | 72B dense | ~43 GB | 48 GB | 32k→128k | Apache 2.0 | `Qwen/Qwen3-72B-GGUF` |
| 3 | **Qwen3-32B** | 32B dense | ~20 GB | 24 GB | 32k→128k | Apache 2.0 | `Qwen/Qwen3-32B-GGUF` (+ `bartowski`, `unsloth`) |
| 4 | **Qwen3.8-27B** | 27B dense (hybrid attention) | 16.5 GB | 20-24 GB | 262k | Apache 2.0 | `qtum/Qwen3.8-27B-GGUF` |
| 5 | **Mistral Small 3.1** | 24B dense | ~14 GB | 16-20 GB | 128k | Apache 2.0 | `bartowski` mirror of `mistralai/Mistral-Small-3.1-24B-Instruct-2501` |
| 6 | **gpt-oss 20B** (MoE, 3.6B active) | 21B total | ~12 GB | 16 GB | 128k | MIT | `openai/gpt-oss-20b` (native MXFP4, quant mirrors available) |
| 7 | **Qwen3-14B** | 14B dense | 9.0 GB | 12 GB | 32k→128k | Apache 2.0 | `Qwen/Qwen3-14B-GGUF` (+ `second-state`, `6block`) |
| 8 | **Qwen3-8B** | 8B dense | ~4.7 GB | 6-8 GB | 32k→128k | Apache 2.0 | `Qwen/Qwen3-8B-GGUF` (+ `bartowski`, `unsloth`) |
| 9 | **Qwen3-4B** ⭐ shipped default | 4B dense | **2.49 GB** | 4 GB | 32k→128k | Apache 2.0 | `Qwen/Qwen3-4B-GGUF` |
| 10 | **Qwen3-1.7B** | 1.7B dense | ~1.2 GB | 2 GB | 32k→128k | Apache 2.0 | `Qwen/Qwen3-1.7B-GGUF` (+ `bartowski`) |

Sizes are approximate `Q4_K_M` file sizes; add ~1.5-2 GB on top for KV cache + llamafile
runtime. Sources: official Qwen GGUF repos, ModelFit quant tables, model cards (May-Sep 2026).

## Which one should I use?

| Your machine | Pick | Why |
|---|---|---|
| Any (verified) | **Qwen3-4B Q4_K_M** | The model IntrovertSOC was built and live-tested against — fits everywhere |
| 8 GB RAM | Qwen3-8B Q4_K_M | Noticeably sharper triage/summaries; still cheap |
| 16 GB RAM | Qwen3-14B Q4_K_M | Good structured-output reliability for JSON steps |
| 24 GB RAM | Qwen3-32B Q4_K_M or Qwen3.8-27B | Best reasoning per GB on consumer hardware |
| 48 GB+ RAM | Qwen3-72B Q4_K_M | Flagship-class analysis, heaviest entry |

Notes for this project specifically:

- **Structured JSON steps matter more than chat sparkle.** Our `complete_json` path repairs and
  retries, but Q4_K_M of 8B+ keeps malformed-JSON retries rare. Below 4B, expect occasional
  repair retries (handled, just slower).
- **`enable_thinking: false`** is sent on every request (llamafile ≥0.10 quirk: Qwen3-family
  templates otherwise stream reasoning into `reasoning_content` and leave `content` empty).
  Non-Qwen templates ignore the extra kwarg.
- **Llama 4 Scout** has the biggest context but is heavy and slower per token (MoE all-experts
  resident); choose it only for whole-corpus analysis on 64 GB+ machines.
- **gpt-oss** is listed for completeness; llamafile 0.10.6 supports it, but verify your build —
  if `Test connection` fails with a template error, stick to the Qwen entries.

## How to switch models

1. Download one `.gguf` file (e.g. `huggingface-cli download Qwen/Qwen3-8B-GGUF Qwen3-8B-Q4_K_M.gguf --local-dir ./models`)
2. **Model Settings → GGUF model file** → paste the path (admin) → **Save & re-test**
3. Copy the generated launch command (Windows/macOS/Linux tabs) and run it in a terminal
4. Keep the llamafile terminal open; the status dot turns green when it answers

No API key, no account, no download happens inside IntrovertSOC itself — you bring the file,
the app only talks to `127.0.0.1`.
