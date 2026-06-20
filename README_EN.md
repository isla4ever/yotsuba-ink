# nanochat-dgxspark-rl

**A Lightweight RL Training Framework for LLMs on NVIDIA DGX Spark**

[Chinese / 中文](README.md)

A minimal yet fully-featured LLM training framework supporting LoRA SFT fine-tuning, GRPO reinforcement learning, and Search-R1 multi-turn search-augmented reasoning. Purpose-built for single-node and dual-node DGX Spark clusters, ready to use out of the box.

---

## Features

| Feature | Single Node | Dual-Node DDP |
|---------|-------------|---------------|
| **LoRA SFT Fine-tuning** | `sft_single_node.sh` | `sft_2node.sh` |
| **GRPO Reinforcement Learning** | `grpo_single_node.sh` | `grpo_2node.sh` |
| **Search-R1 Multi-turn Search Reasoning** | `search_r1_single_node.sh` | `search_r1_2node.sh` |

- Built on HuggingFace Transformers + PEFT, supports loading any HF model (Qwen, LLaMA, etc.)
- LoRA parameter-efficient fine-tuning (trains only ~0.5% of parameters)
- Base model as reference model, no extra VRAM needed (switched via `disable_adapter`)
- Multi-turn search rollout: model generates -> detects `<search>` tags -> executes real search -> injects results -> continues generation
- Search result loss masking: search result tokens are excluded from gradient computation
- SwanLab experiment logging
- Full model save and restore

---

## Project Structure

```
nanochat-dgxspark-rl/
|-- nanochat/                      # nanochat core library (from the nanochat project)
|   |-- __init__.py
|   |-- common.py                  # Distributed init, print0, DummyWandb
|   |-- hf_model_wrapper.py        # HFModelWrapper + LoRA + DistAdamW
|   |-- hf_tokenizer_wrapper.py    # HFTokenizerWrapper + special tokens
|   `-- optim.py                   # MuonAdamW / DistMuonAdamW optimizers
|-- tools/                         # Search tools (from nanochat/tools)
|   |-- search_tools.py            # Search engines (DuckDuckGo/Tavily/Serper/Gemini/Mock)
|   `-- memory_manager.py          # Conversation memory management
|-- tasks/                         # Task definitions (from nanochat/tasks)
|   |-- common.py                  # Base Task class
|   |-- custom_jsonl.py            # JSONL format RL task
|   `-- search_r1.py               # Search-R1 multi-turn search task
|-- scripts/                       # Training scripts (consistent with original nanochat scripts)
|   |-- sft.py                     # LoRA SFT training (DDP + gradient checkpointing)
|   |-- grpo.py                    # GRPO RL training (DistAdamW)
|   |-- search_r1_grpo.py          # Search-R1 multi-turn GRPO training
|   |-- generate_search_r1_data_with_gemini.py   # Generate training data with Gemini
|   |-- generate_search_r1_multiturn_data.py     # Generate multi-turn data with Gemini+DuckDuckGo
|   `-- gen_val_gemini.py          # Generate validation data with Gemini
|-- examples/                      # DGX Spark launch scripts (single-node & dual-node)
|   |-- sft_single_node.sh
|   |-- sft_2node.sh
|   |-- grpo_single_node.sh
|   |-- grpo_2node.sh
|   |-- search_r1_single_node.sh
|   `-- search_r1_2node.sh
|-- data/                          # Sample data
|   |-- gsm8k_mini_test.jsonl      # GSM8K math reasoning examples
|   |-- search_r1_demo.jsonl       # Search-R1 Chinese multi-turn search examples
|   `-- sft_demo.jsonl             # SFT Chinese conversation examples
|-- requirements.txt
|-- pyproject.toml
`-- README.md
```

> **Relationship with nanochat**: This project extracts core components such as HFModelWrapper, HFTokenizerWrapper, and compute_init from [nanochat](https://github.com/karpathy/nanochat). The training scripts maintain the same structure and interfaces as the original nanochat code. The project is fully self-contained and can run without installing nanochat separately.

---

## Environment Setup

### Option 1: pip install

```bash
git clone https://github.com/your-org/nanochat-dgxspark-rl.git
cd nanochat-dgxspark-rl
pip install -e ".[all]"
```

### Option 2: Install dependencies directly

```bash
pip install -r requirements.txt
```

### Core Dependencies

- Python >= 3.9
- PyTorch >= 2.1.0
- Transformers >= 4.40.0
- PEFT >= 0.11.0
- duckduckgo-search >= 6.0.0 (required for Search-R1)
- swanlab >= 0.3.0 (optional, experiment logging)

---

## User Configuration

Before running training, you need to modify the following configurations according to your environment:

### Required Configuration

| Config | Description | How to Set |
|--------|-------------|------------|
| **Model path** | HuggingFace model name or local path | Script argument `--model-path`, e.g. `Qwen/Qwen3-8B` or local path `/path/to/model` |
| **Training data** | JSONL format training data file | Script argument `--data` (SFT), `--task` (GRPO), `--train-data` (Search-R1) |
| **Output directory** | Model save path | Script argument `--output-dir`, default `outputs/sft` |

### Distributed Training Configuration (Dual-Node)

| Config | Description | How to Set |
|--------|-------------|------------|
| **MASTER_ADDR** | Master node IP address | Environment variable, replace with your master node's actual IP |
| **MASTER_PORT** | Communication port | Environment variable, default `29500` |
| **NODE_RANK** | Node number (master node 0, worker node 1) | Environment variable |
| **NCCL_SOCKET_IFNAME** | Network interface name | Environment variable, set according to actual network interface (e.g. `eth0`, `enp226s0`) |

### Search Engine Configuration (Required for Search-R1)

| Config | Description | How to Set |
|--------|-------------|------------|
| **Search proxy** | HTTP proxy address (if needed to access search engines) | Script argument `--search-proxy` or environment variable `SEARCH_PROXY` |
| **TAVILY_API_KEY** | Tavily search engine API key (optional) | Environment variable |
| **SERPER_API_KEY** | Serper search engine API key (optional) | Environment variable |
| **GEMINI_API_KEY** | Gemini API key (optional) | Environment variable |
| **GEMINI_API_URL** | Gemini API URL (optional) | Environment variable |

> **Search engine priority**: DuckDuckGo is used by default (free, no API key required). For more stable search services, configure Tavily or Serper API keys.

### Experiment Logging Configuration (Optional)

| Config | Description | How to Set |
|--------|-------------|------------|
| **SwanLab mode** | Logging mode | Script argument `--swanlab-mode` (`cloud`/`local`/`offline`/`disabled`) |
| **wandb** | GRPO script supports wandb | Script argument `--run` (set to `dummy` to disable) |

### Configuration Examples

```bash
# Simplest single-node SFT training (just specify model and data)
python scripts/sft.py \
    --model-path /path/to/your/model \
    --data /path/to/your/data.jsonl \
    --output-dir outputs/my_sft

# Search-R1 training (with search proxy)
export SEARCH_PROXY=http://your-proxy:port
python scripts/search_r1_grpo.py \
    --model-path /path/to/your/model \
    --train-data /path/to/search_r1_data.jsonl \
    --search-engine duckduckgo \
    --search-proxy $SEARCH_PROXY

# Dual-node distributed training (run on both nodes separately)
export MASTER_ADDR=<your-master-node-ip>
export MASTER_PORT=29500
export NODE_RANK=0  # 0 for master node, 1 for worker node
torchrun --nproc_per_node=1 --nnodes=2 \
    --node_rank=$NODE_RANK --master_addr=$MASTER_ADDR --master_port=$MASTER_PORT \
    scripts/sft.py --model-path /path/to/model --data /path/to/data.jsonl
```

---

## Quick Start

### 1. LoRA SFT Fine-tuning

SFT (Supervised Fine-Tuning) uses annotated conversation data to fine-tune the model with supervision.

**Data format** (JSONL, one entry per line):

```json
{"messages": [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hello! How can I help you?"}]}
```

**Single-node training:**

```bash
python scripts/sft.py \
    --model-path Qwen/Qwen3-8B \
    --data data/sft_demo.jsonl \
    --output-dir outputs/sft \
    --num-epochs 2 \
    --lr 5e-5 \
    --lora-r 16 \
    --lora-alpha 32 \
    --batch-size 1 \
    --grad-accum 4 \
    --max-seq-len 4096

# Or use the launch script:
bash examples/sft_single_node.sh
```

**Dual-node distributed training (2x DGX Spark):**

```bash
# Node 0 (master):
MASTER_ADDR=<NODE0_IP> NODE_RANK=0 bash examples/sft_2node.sh

# Node 1 (worker):
MASTER_ADDR=<NODE0_IP> NODE_RANK=1 bash examples/sft_2node.sh
```

After training, the LoRA adapter is saved in the `outputs/sft/final/` directory.

---

### 2. GRPO Reinforcement Learning

GRPO (Group Relative Policy Optimization) is a policy optimization algorithm based on group-relative advantages, used to train models through reward signals.

**Data format** (JSONL):

```json
{"messages": [{"role": "user", "content": "Natalia sold 48 hair clips to friends..."}], "answer": "72"}
```

**Single-node training:**

```bash
python scripts/grpo.py \
    --model-path Qwen/Qwen3-8B \
    --task data/gsm8k_mini_test.jsonl \
    --output-dir outputs/grpo \
    --num-generations 4 \
    --beta 0.01 \
    --clip-eps 0.2 \
    --lr 5e-5

# Or use the launch script:
bash examples/grpo_single_node.sh
```

**Dual-node distributed training:**

```bash
# Node 0:
MASTER_ADDR=<NODE0_IP> NODE_RANK=0 bash examples/grpo_2node.sh

# Node 1:
MASTER_ADDR=<NODE0_IP> NODE_RANK=1 bash examples/grpo_2node.sh
```

---

### 3. Search-R1 Multi-turn Search Reasoning

Search-R1 is the core highlight of this framework, training models to autonomously use search tools for multi-step reasoning:

```
User: What is the difference between quantum computing and traditional computers?

Model: <think>I need to understand the basic principles of quantum computing</think>
       <search>quantum computing principles qubits</search>
       <information>[Search results automatically injected]</information>
       <think>Based on the search results, quantum computing uses qubits... need to compare</think>
       <search>quantum computing vs traditional computers advantages comparison</search>
       <information>[Search results automatically injected]</information>
       <think>Combining the above information...</think>
       The main differences between quantum computing and traditional computers are...
```

**Data format** (JSONL):

```json
{
  "question": "Who won the 2024 Nobel Prize in Physics?",
  "answer": "machine learning, artificial neural networks, John Hopfield, Geoffrey Hinton",
  "num_hops": 2,
  "difficulty": "medium",
  "search_chain": [
    {"query": "2024 Nobel Prize Physics winners", "purpose": "find the winners"},
    {"query": "Hopfield Hinton research contributions", "purpose": "understand specific research"}
  ]
}
```

**Single-node training:**

```bash
python scripts/search_r1_grpo.py \
    --model-path Qwen/Qwen3-8B \
    --train-data data/search_r1_demo.jsonl \
    --search-engine duckduckgo \
    --search-proxy http://your-proxy:7890 \
    --max-search-turns 5 \
    --num-generations 4 \
    --output-dir outputs/search_r1

# Or use the launch script:
bash examples/search_r1_single_node.sh

# With search proxy:
SEARCH_PROXY=http://your-proxy:7890 bash examples/search_r1_single_node.sh
```

**Dual-node distributed training:**

```bash
# Node 0:
MASTER_ADDR=<NODE0_IP> NODE_RANK=0 \
    SEARCH_PROXY=http://your-proxy:7890 \
    bash examples/search_r1_2node.sh

# Node 1:
MASTER_ADDR=<NODE0_IP> NODE_RANK=1 \
    SEARCH_PROXY=http://your-proxy:7890 \
    bash examples/search_r1_2node.sh
```

> **Note**: The search proxy is only used for search engine requests and does not affect other network services such as SwanLab.

---

## Training Data Generation

This project provides three scripts for generating Search-R1 training and validation data, using the Gemini API to generate questions and combining real search engines to obtain search results.

### Environment Variable Configuration

All data generation scripts require the following environment variables:

```bash
export GEMINI_API_URL="https://your-gemini-api-endpoint/v1/chat/completions"
export GEMINI_API_KEY="your-api-key"
export GEMINI_MODEL="gemini-3-flash-preview"  # Optional, default already set
```

### Method 1: Generate Basic Training Data with Gemini

Use Gemini to generate questions and answer keywords (without real search results):

```bash
python scripts/generate_search_r1_data_with_gemini.py \
    --output data/search_r1_train_gemini.jsonl \
    --num-examples 200
```

### Method 2: Generate Multi-turn Training Data with Gemini + DuckDuckGo (Recommended)

Three-step pipeline: Gemini generates questions -> DuckDuckGo performs real search -> Gemini synthesizes complete multi-turn reasoning responses:

```bash
python scripts/generate_search_r1_multiturn_data.py \
    --output data/search_r1_multiturn_train.jsonl \
    --num-examples 200 \
    --proxy http://your-proxy:port

# Also generate validation set:
python scripts/generate_search_r1_multiturn_data.py \
    --output data/search_r1_multiturn_train.jsonl \
    --num-examples 200 \
    --proxy http://your-proxy:port \
    --gen-val \
    --val-output data/search_r1_multiturn_val.jsonl \
    --val-examples 50
```

### Method 3: Generate Validation Data with Gemini Search Engine

When DuckDuckGo proxy is unavailable, use Gemini to simulate a search engine for generating validation data:

```bash
python scripts/gen_val_gemini.py
```

> **Data quality note**: Method 2 produces the highest quality data because it uses real search engine results. Methods 1 and 3 use Gemini to generate/simulate search results, which may have less accurate information.

---

## Dual-Node DGX Spark Distributed Training Tutorial

This project is purpose-built for NVIDIA DGX Spark (GB10 Grace Blackwell). Below is the complete dual-node deployment workflow.

### Hardware Architecture

```
+-------------------+              +-------------------+
|  DGX Spark #0     |  QSFP/CX7   |  DGX Spark #1     |
|  (Master Node)    |<============>|  (Worker Node)    |
|  GPU: GB10        |   200Gbps    |  GPU: GB10        |
|  torchrun rank=0  |    NCCL      |  torchrun rank=1  |
+-------------------+              +-------------------+
```

### Step 1: Hardware Connection

Follow the official NVIDIA tutorial to complete the physical connection and NCCL test for two DGX Sparks:

1. Stacked connection: https://build.nvidia.com/spark/connect-two-sparks/stacked-sparks
2. NCCL test: https://build.nvidia.com/spark/nccl

### Step 2: Configure Network Environment

**Master Node (Node 0):**

```bash
NODE_RANK=0
IB_IF=$(/usr/sbin/ibdev2netdev | awk '/(Up|ACTIVE)/{print $5; exit}')
MASTER_ADDR=$(ip -o -4 addr show dev "$IB_IF" | awk '{print $4}' | cut -d/ -f1)

export MASTER_ADDR=$MASTER_ADDR
export MASTER_PORT=29500
export NODE_RANK=0
export NCCL_SOCKET_IFNAME=$IB_IF

echo "MASTER_ADDR=$MASTER_ADDR  NODE_RANK=0  IFACE=$IB_IF"
```

**Worker Node (Node 1):**

```bash
NODE_RANK=1
IB_IF=$(/usr/sbin/ibdev2netdev | awk '/(Up|ACTIVE)/{print $5; exit}')
MASTER_ADDR="<master node's MASTER_ADDR>"  # Replace with the address obtained in the previous step

export MASTER_ADDR=$MASTER_ADDR
export MASTER_PORT=29500
export NODE_RANK=1
export NCCL_SOCKET_IFNAME=$IB_IF
```

### Step 3: Launch Training

Execute on both nodes (using SFT as an example):

```bash
# Run on both nodes:
torchrun \
    --nproc_per_node=1 \
    --nnodes=2 \
    --node_rank=${NODE_RANK} \
    --master_addr=${MASTER_ADDR} \
    --master_port=29500 \
    scripts/sft.py \
    --model-path Qwen/Qwen3-8B \
    --data data/sft_demo.jsonl \
    --output-dir outputs/sft_2node
```

> Training will only start after both nodes have launched. The worker node may briefly display connection warnings, which is normal.

### NCCL Tuning Parameters

```bash
export NCCL_IB_DISABLE=0          # Enable InfiniBand
export NCCL_SOCKET_IFNAME=eth0    # Network interface
export NCCL_DEBUG=INFO            # Debug logging
export NCCL_P2P_DISABLE=0         # Enable P2P
```

---

## Key Parameters

### Common Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--model-path` | Required | HuggingFace model name or local path |
| `--lora-r` | 16 | LoRA rank |
| `--lora-alpha` | 32 | LoRA alpha |
| `--lr` | 5e-5 | Learning rate |
| `--dtype` | bfloat16 | Training precision |
| `--swanlab-mode` | cloud | SwanLab logging mode (cloud/local/offline/disabled) |

### GRPO Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--num-generations` | 4 | Number of completions per prompt (G) |
| `--beta` | 0.01 | KL divergence penalty coefficient |
| `--clip-eps` | 0.2 | PPO-style clipping range |
| `--advantage-norm` | zscore | Advantage normalization method |

### Search-R1 Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--search-engine` | duckduckgo | Search engine backend |
| `--search-proxy` | None | Search proxy (used only for search engine) |
| `--max-search-turns` | 5 | Maximum search turns per completion |

---

## Algorithm Overview

### GRPO Algorithm Flow

For each optimization step:

1. Sample a prompt from the dataset
2. For each prompt, generate G completions using the LoRA policy model
3. Score each completion using the reward function
4. Compute group-relative advantages (z-score normalization)
5. Compute per-token log prob of the policy model
6. Disable LoRA adapter to compute reference model's log prob (no extra VRAM)
7. PPO-style clipped policy gradient + KL penalty
8. Update only LoRA parameters

### Search-R1 Multi-turn Rollout Flow

```
prompt --> generate_segment()
  |-- No <search> tag detected --> End (final answer)
  `-- Detected <search>query</search>
        |-- execute_search(query) --> Call real search engine
        |-- Inject <information>search results</information>
        |-- Mark search_mask[info_tokens] = 0 (exclude from loss)
        `-- Continue generate_segment()
              `-- Repeat until MAX_SEARCH_TURNS reached
```

---

## Acknowledgments

This project would not have been possible without the support of the following projects and communities:

- [nanochat](https://github.com/nanochat/nanochat) -- This project is built on nanochat's core architecture. Thanks to nanochat for providing excellent infrastructure
- [Train nanochat on 2 NVIDIA DGX Sparks](https://gist.github.com/emaadmanzoor/d245c0c0ce90b25b4d50c0ffc448f876) -- Thanks to @emaadmanzoor for the dual-node DGX Spark distributed training tutorial. This project's distributed training approach is based on that tutorial
- [NVIDIA DGX Spark Community](https://build.nvidia.com/spark) -- Thanks to the NVIDIA DGX Spark community for technical support and hardware documentation
- [Search-R1](https://github.com/PeterGriffinJin/Search-R1) -- The original search-augmented reasoning framework
- [TRL](https://github.com/huggingface/trl) -- GRPO algorithm reference implementation
- [PEFT](https://github.com/huggingface/peft) -- LoRA implementation
- [SwanLab](https://swanlab.cn) -- Experiment logging platform

---

## Project Origin

The development workflow of this project was as follows: first, the nanochat project was locally modified and extended to add HuggingFace model LoRA fine-tuning, GRPO reinforcement learning, Search-R1 multi-turn search reasoning, and other features. Single-node and dual-node distributed training were validated on NVIDIA DGX Spark. After confirming all features ran successfully, AI tools were used to organize and refactor the validated code into the current standalone open-source project.

---

## License

Apache 2.0

