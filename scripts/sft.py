"""
LoRA SFT (Supervised Fine-Tuning) for Qwen3 models with DDP distributed training.

Supports single-GPU and multi-node distributed training via torchrun.
Uses LoRA (Low-Rank Adaptation) via PEFT for memory-efficient fine-tuning.
Logging to SwanLab (cloud/local), console, and local JSONL.

Single-GPU usage:
    python scripts/qwen3_lora_sft.py \\
        --model-path /path/to/Qwen3.5-4B \\
        --data data/train.jsonl \\
        --output-dir /path/to/save

Distributed (2x DGX Spark, 1 GPU each, 200G network):
    # On master (node 0):
    torchrun --nproc_per_node=1 --nnodes=2 --node_rank=0 \\
        --master_addr=$MASTER_IP --master_port=29500 \\
        scripts/qwen3_lora_sft.py --model-path /path/to/Qwen3.5-4B --data ...

    # On worker (node 1):
    torchrun --nproc_per_node=1 --nnodes=2 --node_rank=1 \\
        --master_addr=$MASTER_IP --master_port=29500 \\
        scripts/qwen3_lora_sft.py --model-path /path/to/Qwen3.5-4B --data ...

Dataset format: JSONL files with chat messages:
    {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
"""

import argparse
import json
import os
import platform
import sys
import time
import random
import math
import datetime
import gc
from pathlib import Path
from contextlib import nullcontext

# Force unbuffered stdout
os.environ["PYTHONUNBUFFERED"] = "1"
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)


def _patch_windows_wmi_for_torch() -> None:
    """
    Work around Windows WMI hangs when torch imports platform.machine().
    """
    if os.name != "nt":
        return
    try:
        _ = platform._wmi_query  # type: ignore[attr-defined]
    except Exception:
        return

    def _fast_wmi_query(*_args: object, **_kwargs: object):
        return ("10.0.0", 1, "multiprocessor free", 0, 0)

    platform._wmi_query = _fast_wmi_query  # type: ignore[attr-defined]


_patch_windows_wmi_for_torch()

import torch
import torch.nn.functional as F
import torch.distributed as dist
from torch.utils.data import Dataset, DataLoader
from torch.utils.data.distributed import DistributedSampler
from torch.nn.parallel import DistributedDataParallel as DDP

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    get_cosine_schedule_with_warmup,
)
from transformers.utils.import_utils import (
    is_causal_conv1d_available,
    is_flash_linear_attention_available,
)
from peft import (
    LoraConfig,
    get_peft_model,
    TaskType,
)

# ---------------------------------------------------------------------------
# SwanLab integration (graceful fallback)
# ---------------------------------------------------------------------------
try:
    import swanlab
    HAS_SWANLAB = True
except ImportError:
    HAS_SWANLAB = False


# ---------------------------------------------------------------------------
# Distributed helpers
# ---------------------------------------------------------------------------
def is_ddp_run():
    """Check if this is launched by torchrun."""
    return all(k in os.environ for k in ("RANK", "LOCAL_RANK", "WORLD_SIZE"))


def has_xpu():
    """Check Intel XPU availability safely."""
    try:
        return hasattr(torch, "xpu") and torch.xpu.is_available()
    except Exception:
        return False


def setup_distributed():
    """Initialize DDP and return (rank, local_rank, world_size, device)."""
    if is_ddp_run():
        rank = int(os.environ["RANK"])
        local_rank = int(os.environ["LOCAL_RANK"])
        world_size = int(os.environ["WORLD_SIZE"])
        device = torch.device("cuda", local_rank)
        torch.cuda.set_device(device)
        dist.init_process_group(backend="nccl")
        dist.barrier()
        return True, rank, local_rank, world_size, device
    else:
        if torch.cuda.is_available():
            device = torch.device("cuda")
        elif has_xpu():
            device = torch.device("xpu")
        else:
            device = torch.device("cpu")
        return False, 0, 0, 1, device


def cleanup_distributed():
    """Clean up DDP."""
    if dist.is_available() and dist.is_initialized():
        dist.destroy_process_group()


def print0(msg="", **kwargs):
    """Print only on rank 0."""
    if int(os.environ.get("RANK", 0)) == 0:
        try:
            print(msg, flush=True, **kwargs)
        except UnicodeEncodeError:
            # Windows cp936/gbk consoles may fail on emoji.
            enc = sys.stdout.encoding or "utf-8"
            safe_msg = str(msg).encode(enc, errors="replace").decode(enc, errors="replace")
            print(safe_msg, flush=True, **kwargs)


def reduce_mean(tensor, world_size):
    """All-reduce a tensor and return the mean."""
    if world_size <= 1:
        return tensor
    t = tensor.clone()
    dist.all_reduce(t, op=dist.ReduceOp.SUM)
    return t / world_size


# ---------------------------------------------------------------------------
# Training logger
# ---------------------------------------------------------------------------
class TrainingLogger:
    def __init__(self, output_dir, project="nanochat-lora-sft", experiment_name=None,
                 config=None, swanlab_mode="local", log_file="training_log.jsonl",
                 is_master=True):
        self.output_dir = output_dir
        self.log_file_path = os.path.join(output_dir, log_file)
        self.is_master = is_master
        self.swanlab_run = None

        if not is_master:
            return

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Initialize SwanLab only on master
        if HAS_SWANLAB and swanlab_mode != "disabled":
            try:
                self.swanlab_run = swanlab.init(
                    project=project,
                    experiment_name=experiment_name or f"lora-sft-{datetime.datetime.now().strftime('%m%d_%H%M')}",
                    config=config or {},
                    mode=swanlab_mode,
                    logdir=os.path.join(output_dir, "swanlog"),
                )
                print0(f"  ✅ SwanLab initialized (mode={swanlab_mode})")
            except Exception as e:
                print0(f"  ⚠️  SwanLab init failed: {e}")
                self.swanlab_run = None
        elif swanlab_mode == "disabled":
            print0("  ℹ️  SwanLab disabled")

    def log(self, metrics: dict, step: int = None):
        if not self.is_master:
            return
        record = {"step": step, "timestamp": time.time(), **metrics}
        if self.swanlab_run is not None:
            try:
                swanlab.log(metrics, step=step)
            except Exception:
                pass
        try:
            with open(self.log_file_path, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception:
            pass

    def log_summary(self, metrics: dict):
        if not self.is_master:
            return
        if self.swanlab_run is not None:
            try:
                swanlab.log(metrics)
            except Exception:
                pass

    def finish(self):
        if not self.is_master:
            return
        if self.swanlab_run is not None:
            try:
                swanlab.finish()
            except Exception:
                pass
        print0(f"  📊 Training log saved to: {self.log_file_path}")


class ProgressBar:
    def __init__(self, total, prefix="", width=40):
        self.total = total
        self.prefix = prefix
        self.width = width
        self.start_time = time.time()

    def update(self, current, loss=None, lr=None):
        elapsed = time.time() - self.start_time
        frac = current / max(self.total, 1)
        filled = int(self.width * frac)
        # Keep progress bar ASCII-only for Windows GBK terminals.
        bar = "#" * filled + "-" * (self.width - filled)
        pct = frac * 100
        eta = elapsed / current * (self.total - current) if current > 0 else 0
        parts = [f"\r  {self.prefix} |{bar}| {pct:5.1f}% [{current}/{self.total}]"]
        if loss is not None:
            parts.append(f"loss={loss:.4f}")
        if lr is not None:
            parts.append(f"lr={lr:.2e}")
        parts.append(f"eta={eta:.0f}s")
        line = " | ".join(parts)
        try:
            print(line, end="", flush=True)
        except UnicodeEncodeError:
            enc = sys.stdout.encoding or "utf-8"
            safe_line = line.encode(enc, errors="replace").decode(enc, errors="replace")
            print(safe_line, end="", flush=True)

    def finish(self):
        print(flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="LoRA SFT for Qwen3 (DDP distributed)")
parser.add_argument("--model-path", type=str, required=True)
parser.add_argument("--data", type=str, nargs="+", required=True)
parser.add_argument("--val-data", type=str, nargs="*", default=None)
parser.add_argument("--output-dir", type=str, default="outputs/sft")
# Optimized training hyperparameters (based on analysis of previous run)
parser.add_argument("--num-epochs", type=int, default=1)
parser.add_argument("--lr", type=float, default=2e-5,
                    help="Learning rate (RTX 3080/Qwen3.5-4B safe default)")
parser.add_argument("--batch-size", type=int, default=1,
                    help="Per-device micro batch size")
parser.add_argument("--grad-accum", type=int, default=32,
                    help="Gradient accumulation steps (effective batch = batch_size * grad_accum * world_size)")
parser.add_argument("--max-seq-len", type=int, default=256)
parser.add_argument("--truncate-side", type=str, default="head", choices=["head", "tail"],
                    help="Truncate from head (keep prefix) or tail (keep ending/assistant).")
parser.add_argument("--warmup-ratio", type=float, default=0.05)
parser.add_argument("--weight-decay", type=float, default=0.01)
parser.add_argument("--max-grad-norm", type=float, default=1.0)
# Optimized LoRA hyperparameters (reduced from r=64 to r=16 for small data)
parser.add_argument("--lora-r", type=int, default=4,
                    help="LoRA rank (RTX 3080/Qwen3.5-4B safe default)")
parser.add_argument("--lora-alpha", type=int, default=8,
                    help="LoRA alpha (scaling = alpha/r)")
parser.add_argument("--lora-dropout", type=float, default=0.05,
                    help="LoRA dropout (higher for regularization with small data)")
parser.add_argument("--lora-target", type=str, nargs="+",
                    default=["q_proj"])
# SwanLab & logging
parser.add_argument("--swanlab-mode", type=str, default="cloud",
                    choices=["cloud", "local", "offline", "disabled"])
parser.add_argument("--swanlab-project", type=str, default="nanochat-lora-sft")
parser.add_argument("--run-name", type=str, default=None)
# Misc
parser.add_argument("--seed", type=int, default=42)
parser.add_argument("--log-every", type=int, default=5)
parser.add_argument("--save-every-epoch", dest="save_every_epoch", action="store_true")
parser.add_argument("--no-save-every-epoch", dest="save_every_epoch", action="store_false")
parser.set_defaults(save_every_epoch=True)
parser.add_argument("--dtype", type=str, default="float16",
                    choices=["bfloat16", "float16", "float32"])
parser.add_argument("--attn-implementation", type=str, default="auto",
                    choices=["auto", "sdpa", "eager"],
                    help="Attention kernel for full-attention layers. 'auto' uses sdpa on CUDA, eager otherwise.")
args = parser.parse_args()


# ---------------------------------------------------------------------------
# Setup distributed
# ---------------------------------------------------------------------------
use_ddp, rank, local_rank, world_size, device = setup_distributed()
is_master = (rank == 0)

def set_seed(seed):
    random.seed(seed + rank)  # different seed per rank for data sampling diversity
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if has_xpu():
        try:
            torch.xpu.manual_seed_all(seed)
        except Exception:
            pass

set_seed(args.seed)

dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
ptdtype = dtype_map[args.dtype]


def resolve_attn_implementation(requested: str, device: torch.device) -> str:
    if requested != "auto":
        return requested
    if device.type == "cuda":
        return "sdpa"
    return "eager"


selected_attn_implementation = resolve_attn_implementation(args.attn_implementation, device)

if device.type == "cuda" and torch.cuda.is_available():
    try:
        torch.backends.cuda.enable_flash_sdp(True)
        torch.backends.cuda.enable_mem_efficient_sdp(True)
        torch.backends.cuda.enable_math_sdp(True)
    except Exception:
        pass


def autocast_ctx(device: torch.device, dtype: torch.dtype):
    if device.type == "cuda":
        return torch.amp.autocast(device_type="cuda", dtype=dtype)
    if device.type == "xpu":
        try:
            return torch.amp.autocast(device_type="xpu", dtype=dtype)
        except Exception:
            return nullcontext()
    return nullcontext()


def memory_allocated_gb(device: torch.device):
    if device.type == "cuda" and torch.cuda.is_available():
        return torch.cuda.memory_allocated() / 1024**3
    if device.type == "xpu" and has_xpu():
        try:
            return torch.xpu.memory_allocated() / 1024**3
        except Exception:
            return 0.0
    return 0.0


def memory_peak_gb(device: torch.device):
    if device.type == "cuda" and torch.cuda.is_available():
        return torch.cuda.max_memory_allocated() / 1024**3
    if device.type == "xpu" and has_xpu():
        try:
            return torch.xpu.max_memory_allocated() / 1024**3
        except Exception:
            return 0.0
    return 0.0


def maybe_empty_cache(device: torch.device) -> None:
    gc.collect()
    if device.type == "xpu" and has_xpu():
        try:
            torch.xpu.empty_cache()
            torch.xpu.synchronize()
        except Exception:
            pass
    if device.type == "cuda" and torch.cuda.is_available():
        try:
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        except Exception:
            pass

# Effective batch size = per_device_batch * grad_accum * world_size
effective_batch = args.batch_size * args.grad_accum * world_size

print0("=" * 70)
print0("  🚀 LoRA SFT Training for Qwen3")
if use_ddp:
    print0(f"  🌐 Distributed: {world_size} device(s) (rank {rank}, local_rank {local_rank})")
print0("=" * 70)
print0(f"  Model:           {args.model_path}")
print0(f"  Data files:      {args.data}")
print0(f"  Output:          {args.output_dir}")
print0(f"  Epochs:          {args.num_epochs}")
print0(f"  LR:              {args.lr}")
print0(f"  Batch size:      {args.batch_size} x {args.grad_accum} (accum) x {world_size} (devices) = {effective_batch} effective")
print0(f"  Max seq len:     {args.max_seq_len}")
print0(f"  Truncate side:   {args.truncate_side}")
print0(f"  LoRA r/α:        {args.lora_r}/{args.lora_alpha} (scaling={args.lora_alpha/args.lora_r:.1f}x)")
print0(f"  LoRA targets:    {args.lora_target}")
print0(f"  LoRA dropout:    {args.lora_dropout}")
print0(f"  Weight decay:    {args.weight_decay}")
print0(f"  Device:          {device}")
print0(f"  Dtype:           {args.dtype}")
print0(f"  Attention impl:  {selected_attn_implementation}")
if device.type == "cuda":
    print0(
        f"  Linear fast path: flash_linear_attention={is_flash_linear_attention_available()} "
        f"causal_conv1d={is_causal_conv1d_available()}"
    )
print0(f"  SwanLab mode:    {args.swanlab_mode}")
print0("=" * 70)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class ChatSFTDataset(Dataset):
    """SFT dataset: tokenizes chat conversations, masks non-assistant tokens."""

    def __init__(self, jsonl_files, tokenizer, max_seq_len=4096, truncate_side="head", silent=False):
        self.tokenizer = tokenizer
        self.max_seq_len = max_seq_len
        self.truncate_side = truncate_side
        self.examples = []
        self.skipped_bad_messages = 0
        self.skipped_replacement_char = 0

        for fpath in jsonl_files:
            file_count = 0
            if not silent:
                print0(f"  📂 Loading {fpath}...")
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "messages" not in obj or not isinstance(obj["messages"], list):
                        continue
                    messages = obj["messages"]
                    if not all(isinstance(m, dict) and isinstance(m.get("role"), str) and isinstance(m.get("content"), str) for m in messages):
                        self.skipped_bad_messages += 1
                        continue
                    if any("\ufffd" in m.get("content", "") for m in messages):
                        self.skipped_replacement_char += 1
                        continue
                    self.examples.append(messages)
                    file_count += 1
            if not silent:
                print0(f"    → {file_count} examples loaded")

        if not silent:
            print0(f"  📊 Total: {len(self.examples)} examples from {len(jsonl_files)} file(s)")

        if not silent:
            if self.skipped_bad_messages:
                print0(f"  Skipped bad message rows: {self.skipped_bad_messages}")
            if self.skipped_replacement_char:
                print0(f"  Skipped rows with replacement char: {self.skipped_replacement_char}")

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        messages = self.examples[idx]

        # Filter empty system messages
        filtered = [m for m in messages if not (m["role"] == "system" and not m["content"].strip())]
        if not filtered:
            filtered = messages

        # Build prefix (up to first assistant turn) for masking
        prefix_messages = []
        for msg in filtered:
            if msg["role"] == "assistant":
                break
            prefix_messages.append(msg)

        # Tokenize via chat template
        full_text = self.tokenizer.apply_chat_template(
            filtered, tokenize=False, add_generation_prompt=False
        )
        prefix_text = self.tokenizer.apply_chat_template(
            prefix_messages, tokenize=False, add_generation_prompt=True
        )

        full_ids_all = self.tokenizer.encode(full_text, add_special_tokens=False)
        prefix_ids = self.tokenizer.encode(prefix_text, add_special_tokens=False)

        # Labels on the full sequence: -100 for prefix, token ids for assistant text.
        prefix_len_all = min(len(prefix_ids), len(full_ids_all))
        labels_all = [-100] * prefix_len_all + full_ids_all[prefix_len_all:]

        # Truncate input and labels with the same window.
        if len(full_ids_all) > self.max_seq_len:
            if self.truncate_side == "tail":
                full_ids = full_ids_all[-self.max_seq_len:]
                labels = labels_all[-self.max_seq_len:]
            else:
                full_ids = full_ids_all[:self.max_seq_len]
                labels = labels_all[:self.max_seq_len]
        else:
            full_ids = full_ids_all
            labels = labels_all

        assert len(full_ids) == len(labels)
        return {"input_ids": full_ids, "labels": labels}


# ---------------------------------------------------------------------------
# [1/5] Load tokenizer
# ---------------------------------------------------------------------------
print0("\n[1/5] 🔤 Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(
    args.model_path, trust_remote_code=True, padding_side="right"
)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
print0(f"  Vocab size: {len(tokenizer)}")
print0(f"  Pad token:  {tokenizer.pad_token} (id={tokenizer.pad_token_id})")


def collate_fn(batch):
    """Pad sequences to same length within a batch."""
    max_len = max(len(ex["input_ids"]) for ex in batch)
    input_ids_batch, labels_batch, attn_mask_batch = [], [], []
    for ex in batch:
        pad_len = max_len - len(ex["input_ids"])
        input_ids_batch.append(ex["input_ids"] + [tokenizer.pad_token_id] * pad_len)
        labels_batch.append(ex["labels"] + [-100] * pad_len)
        attn_mask_batch.append([1] * len(ex["input_ids"]) + [0] * pad_len)
    return {
        "input_ids": torch.tensor(input_ids_batch, dtype=torch.long),
        "labels": torch.tensor(labels_batch, dtype=torch.long),
        "attention_mask": torch.tensor(attn_mask_batch, dtype=torch.long),
    }


# ---------------------------------------------------------------------------
# [2/5] Load dataset
# ---------------------------------------------------------------------------
print0("\n[2/5] 📁 Loading datasets...")
train_dataset = ChatSFTDataset(
    args.data, tokenizer, max_seq_len=args.max_seq_len, truncate_side=args.truncate_side
)

val_dataset = None
if args.val_data:
    print0("  Loading validation data...")
    val_dataset = ChatSFTDataset(
        args.val_data,
        tokenizer,
        max_seq_len=args.max_seq_len,
        truncate_side=args.truncate_side,
        silent=True,
    )

# DDP-aware data loading
if use_ddp:
    train_sampler = DistributedSampler(
        train_dataset, num_replicas=world_size, rank=rank, shuffle=True, seed=args.seed
    )
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, sampler=train_sampler,
        collate_fn=collate_fn, num_workers=2, pin_memory=True, drop_last=False,
    )
else:
    train_sampler = None
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True,
        collate_fn=collate_fn, num_workers=0, pin_memory=True, drop_last=False,
    )

# Dataset statistics (on master only, sample first 50)
if is_master:
    seq_lengths, train_token_counts = [], []
    for i in range(min(50, len(train_dataset))):
        sample = train_dataset[i]
        seq_lengths.append(len(sample["input_ids"]))
        train_token_counts.append(sum(1 for l in sample["labels"] if l != -100))
    avg_seq_len = sum(seq_lengths) / len(seq_lengths)
    avg_train_tokens = sum(train_token_counts) / len(train_token_counts)
    print0(f"  📊 Dataset stats (sampled {len(seq_lengths)} examples):")
    print0(f"     Avg sequence length:  {avg_seq_len:.0f} tokens")
    print0(f"     Avg trainable tokens: {avg_train_tokens:.0f} tokens")
    print0(f"     Max sequence length:  {max(seq_lengths)} tokens")
    print0(f"     Min sequence length:  {min(seq_lengths)} tokens")
else:
    avg_train_tokens = 2500  # approximate fallback


# ---------------------------------------------------------------------------
# [3/5] Load model + LoRA
# ---------------------------------------------------------------------------
print0("\n[3/5] 🧠 Loading model and applying LoRA...")
t0 = time.time()

# For DDP/CUDA, load model on specific device. For XPU, move after load.
device_map = {"": local_rank} if device.type == "cuda" else None
model_load_kwargs = {
    "torch_dtype": ptdtype,
    "trust_remote_code": True,
    "device_map": device_map,
    "attn_implementation": selected_attn_implementation,
}
try:
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        **model_load_kwargs,
    )
except Exception as exc:
    if selected_attn_implementation != "eager":
        print0(f"  Attention impl {selected_attn_implementation} failed during load: {exc}")
        print0("  Falling back to eager attention for compatibility")
        model_load_kwargs["attn_implementation"] = "eager"
        selected_attn_implementation = "eager"
        model = AutoModelForCausalLM.from_pretrained(
            args.model_path,
            **model_load_kwargs,
        )
    else:
        raise
if device.type == "xpu":
    model = model.to(device)
load_time = time.time() - t0
base_params = sum(p.numel() for p in model.parameters())
print0(f"  Base model loaded in {load_time:.1f}s")
print0(f"  Base model params: {base_params:,} ({base_params/1e9:.2f}B)")
print0(f"  Active attention: {selected_attn_implementation}")

# Configure LoRA
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=args.lora_r,
    lora_alpha=args.lora_alpha,
    lora_dropout=args.lora_dropout,
    target_modules=args.lora_target,
    bias="none",
)

model = get_peft_model(model, lora_config)

trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
all_params = sum(p.numel() for p in model.parameters())
print0(f"  LoRA applied:")
print0(f"    Trainable params: {trainable_params:,} ({trainable_params/1e6:.1f}M)")
print0(f"    All params:       {all_params:,} ({all_params/1e9:.2f}B)")
print0(f"    Trainable ratio:  {trainable_params/all_params*100:.2f}%")

# Enable gradient checkpointing
# Prefer enabling input activation grads without turning embedding weights trainable.
if hasattr(model, "enable_input_require_grads"):
    model.enable_input_require_grads()
else:
    def make_inputs_require_grad(module, input, output):
        if isinstance(output, torch.Tensor):
            output.requires_grad_(True)
    model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
print0(f"  ✅ Gradient checkpointing enabled")

# Wrap with DDP
if use_ddp:
    model = DDP(model, device_ids=[local_rank], output_device=local_rank,
                find_unused_parameters=False)
    print0(f"  ✅ Model wrapped with DistributedDataParallel")

# For saving: get the underlying PEFT model
def get_peft_model_for_save(model):
    """Unwrap DDP to get the PEFT model for saving."""
    if hasattr(model, "module"):
        return model.module  # DDP wrapper
    return model


def build_adapter_state_dict_cpu(peft_model):
    """
    Build a CPU-only adapter state dict to avoid full-model XPU->CPU spikes
    during save_pretrained on low-memory Intel XPU setups.
    """
    state_dict = {}
    for name, param in peft_model.named_parameters():
        if ("lora_" not in name) and ("modules_to_save" not in name):
            continue
        try:
            state_dict[name] = param.detach().to("cpu", copy=True)
        except TypeError:
            state_dict[name] = param.detach().cpu().clone()
    for name, buf in peft_model.named_buffers():
        if ("lora_" in name) or ("modules_to_save" in name):
            state_dict[name] = buf.detach().cpu().clone()
    return state_dict


# ---------------------------------------------------------------------------
# [4/5] Optimizer & Scheduler
# ---------------------------------------------------------------------------
print0("\n[4/5] ⚙️  Setting up optimizer and scheduler...")

# With DDP, each rank processes len(train_loader) batches per epoch
# Steps per epoch = batches per rank / grad_accum
steps_per_epoch = max(1, len(train_loader) // args.grad_accum)
total_steps = steps_per_epoch * args.num_epochs
warmup_steps = int(total_steps * args.warmup_ratio)

# Get parameters from potentially DDP-wrapped model
param_model = model.module if hasattr(model, "module") else model
optim_params = [
    p for n, p in param_model.named_parameters()
    if p.requires_grad and (("lora_" in n) or ("modules_to_save" in n))
]
optimizer = torch.optim.AdamW(
    optim_params, lr=args.lr, weight_decay=args.weight_decay,
    betas=(0.9, 0.999), eps=1e-8,
)
scheduler = get_cosine_schedule_with_warmup(
    optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps,
)

print0(f"  Steps per epoch:     {steps_per_epoch}")
print0(f"  Total optim steps:   {total_steps}")
print0(f"  Warmup steps:        {warmup_steps}")
print0(f"  Effective batch size: {effective_batch}")
est_total_tokens = int(avg_train_tokens * len(train_dataset) * args.num_epochs / world_size)
print0(f"  Est. train tokens (per GPU): {est_total_tokens:,}")

# ---------------------------------------------------------------------------
# Initialize logger (SwanLab + JSON + Console) — master only
# ---------------------------------------------------------------------------
print0("\n  📊 Initializing training logger...")

if args.run_name is None:
    model_short = os.path.basename(args.model_path.rstrip("/"))
    ddp_tag = f"_{world_size}gpu" if use_ddp else ""
    args.run_name = f"{model_short}_r{args.lora_r}_lr{args.lr}{ddp_tag}"

logger = TrainingLogger(
    output_dir=args.output_dir,
    project=args.swanlab_project,
    experiment_name=args.run_name,
    config={
        "model": args.model_path,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "lora_dropout": args.lora_dropout,
        "lora_target_modules": args.lora_target,
        "lr": args.lr,
        "weight_decay": args.weight_decay,
        "num_epochs": args.num_epochs,
        "batch_size": args.batch_size,
        "grad_accum": args.grad_accum,
        "effective_batch_size": effective_batch,
        "max_seq_len": args.max_seq_len,
        "warmup_ratio": args.warmup_ratio,
        "total_steps": total_steps,
        "train_examples": len(train_dataset),
        "trainable_params": trainable_params,
        "trainable_ratio": f"{trainable_params/all_params*100:.2f}%",
        "dtype": args.dtype,
        "seed": args.seed,
        "dataset_files": args.data,
        "distributed": use_ddp,
        "world_size": world_size,
    },
    swanlab_mode=args.swanlab_mode,
    is_master=is_master,
)


# ---------------------------------------------------------------------------
# [5/5] Training loop
# ---------------------------------------------------------------------------
print0(f"\n[5/5] 🏋️  Starting training...")
print0("=" * 70)
print0(f"  {'Epoch':>5} | {'Step':>8} | {'Loss':>10} | {'LR':>10} | {'Tok/s':>8} | {'GPU Mem':>10} | {'ETA':>8}")
print0("-" * 70)

global_step = 0
best_val_loss = float("inf")
total_training_tokens = 0
training_start_time = time.time()
all_epoch_losses = []
oom_skipped_batches = 0

if is_master:
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

for epoch in range(args.num_epochs):
    model.train()

    # Set epoch for DistributedSampler (ensures different shuffle each epoch)
    if train_sampler is not None:
        train_sampler.set_epoch(epoch)

    epoch_loss = 0.0
    epoch_tokens = 0
    epoch_samples = 0
    accum_loss = 0.0
    accum_tokens = 0
    t_epoch = time.time()
    t_step = time.time()

    if is_master:
        pbar = ProgressBar(len(train_loader), prefix=f"Epoch {epoch+1}/{args.num_epochs}")

    for batch_idx, batch in enumerate(train_loader):
        try:
            input_ids = batch["input_ids"].to(device)
            labels = batch["labels"].to(device)
            attention_mask = batch["attention_mask"].to(device)

            # Forward + backward (robust OOM handling on XPU/CUDA)
            with autocast_ctx(device, ptdtype):
                outputs = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels,
                )
                loss = outputs.loss / args.grad_accum

            loss.backward()
        except RuntimeError as e:
            msg = str(e)
            is_oom = (
                "UR_RESULT_ERROR_OUT_OF_RESOURCES" in msg
                or "UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY" in msg
                or "OUT_OF_DEVICE_MEMORY" in msg
                or "out of memory" in msg.lower()
            )
            if not is_oom:
                raise

            oom_skipped_batches += 1
            optimizer.zero_grad(set_to_none=True)

            if device.type == "xpu" and has_xpu():
                try:
                    torch.xpu.empty_cache()
                    torch.xpu.synchronize()
                except Exception:
                    pass
            elif device.type == "cuda":
                try:
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                except Exception:
                    pass

            print0(
                f"  [OOM] Skip batch {batch_idx + 1}/{len(train_loader)} "
                f"(epoch {epoch + 1}), total_skipped={oom_skipped_batches}"
            )
            continue

        # Track metrics (local)
        num_tokens = (labels != -100).sum().item()
        epoch_loss += outputs.loss.item() * num_tokens
        epoch_tokens += num_tokens
        total_training_tokens += num_tokens
        accum_loss += outputs.loss.item()
        accum_tokens += num_tokens
        epoch_samples += input_ids.size(0)

        # Optimizer step
        is_accum_step = (batch_idx + 1) % args.grad_accum == 0
        is_last_batch = (batch_idx + 1) == len(train_loader)

        if is_accum_step or is_last_batch:
            grad_norm = torch.nn.utils.clip_grad_norm_(
                param_model.parameters(), args.max_grad_norm
            ).item()
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            global_step += 1

            # Compute step metrics
            lr_now = scheduler.get_last_lr()[0]
            step_time = time.time() - t_step
            accum_steps = args.grad_accum if is_accum_step else ((batch_idx + 1) % args.grad_accum)
            avg_step_loss = accum_loss / max(accum_steps, 1)
            tokens_per_sec = accum_tokens / max(step_time, 1e-6)

            # Sync loss across ranks for accurate logging
            if use_ddp:
                loss_tensor = torch.tensor([avg_step_loss], device=device)
                loss_tensor = reduce_mean(loss_tensor, world_size)
                avg_step_loss_synced = loss_tensor.item()
            else:
                avg_step_loss_synced = avg_step_loss

            # Device memory
            gpu_mem_gb = memory_allocated_gb(device)
            gpu_peak_gb = memory_peak_gb(device)

            # ETA
            elapsed_total = time.time() - training_start_time
            if global_step > 0:
                eta_sec = elapsed_total / global_step * (total_steps - global_step)
                eta_str = str(datetime.timedelta(seconds=int(eta_sec)))
            else:
                eta_str = "?"

            # Log
            if global_step % args.log_every == 0:
                logger.log({
                    "train/loss": avg_step_loss_synced,
                    "train/lr": lr_now,
                    "train/grad_norm": grad_norm,
                    "train/tokens_per_sec": tokens_per_sec * world_size,  # total throughput
                    "train/gpu_memory_gb": gpu_mem_gb,
                    "train/gpu_peak_memory_gb": gpu_peak_gb,
                    "train/epoch": epoch + (batch_idx + 1) / len(train_loader),
                    "train/total_tokens": total_training_tokens,
                }, step=global_step)

                print0(f"  {epoch+1:>5} | {global_step:>4}/{total_steps:<4}| "
                       f"{avg_step_loss_synced:>10.4f} | {lr_now:>10.2e} | "
                       f"{tokens_per_sec * world_size:>7.0f} | {gpu_mem_gb:>6.1f}GB | "
                       f"{eta_str:>8}")

            # Reset accumulators
            accum_loss = 0.0
            accum_tokens = 0
            t_step = time.time()

        # Progress bar (master only)
        if is_master:
            pbar.update(batch_idx + 1, loss=outputs.loss.item(), lr=scheduler.get_last_lr()[0])

    if is_master:
        pbar.finish()

    # ----- Epoch summary -----
    avg_epoch_loss = epoch_loss / max(epoch_tokens, 1)

    # Sync epoch loss across ranks
    if use_ddp:
        epoch_loss_t = torch.tensor([epoch_loss], device=device)
        epoch_tokens_t = torch.tensor([epoch_tokens], device=device, dtype=torch.float)
        dist.all_reduce(epoch_loss_t, op=dist.ReduceOp.SUM)
        dist.all_reduce(epoch_tokens_t, op=dist.ReduceOp.SUM)
        avg_epoch_loss = (epoch_loss_t / epoch_tokens_t).item()
        total_epoch_tokens = int(epoch_tokens_t.item())
    else:
        total_epoch_tokens = epoch_tokens

    epoch_time = time.time() - t_epoch
    all_epoch_losses.append(avg_epoch_loss)

    print0(f"\n  ✨ Epoch {epoch+1} Summary:")
    print0(f"     Average loss:    {avg_epoch_loss:.4f}")
    print0(f"     Total tokens:    {total_epoch_tokens:,} ({epoch_tokens:,} per GPU)")
    print0(f"     Total samples:   {epoch_samples}")
    print0(f"     Epoch time:      {epoch_time:.1f}s ({epoch_time/60:.1f}min)")
    print0(f"     Throughput:      {total_epoch_tokens/epoch_time:.0f} tok/s (total)")

    logger.log({
        "epoch/train_loss": avg_epoch_loss,
        "epoch/time_seconds": epoch_time,
        "epoch/throughput_tps": total_epoch_tokens / max(epoch_time, 1),
        "epoch/total_tokens": total_epoch_tokens,
    }, step=global_step)

    # ----- Validation -----
    if val_dataset is not None and is_master:
        print0(f"\n  🔍 Running validation...")
        peft_model = get_peft_model_for_save(model)
        peft_model.eval()
        val_loss = 0.0
        val_tokens = 0
        val_loader = DataLoader(val_dataset, batch_size=args.batch_size,
                                shuffle=False, collate_fn=collate_fn)
        with torch.no_grad():
            for vbatch in val_loader:
                vinput_ids = vbatch["input_ids"].to(device)
                vlabels = vbatch["labels"].to(device)
                vattention_mask = vbatch["attention_mask"].to(device)
                with autocast_ctx(device, ptdtype):
                    voutputs = peft_model(
                        input_ids=vinput_ids, attention_mask=vattention_mask, labels=vlabels,
                    )
                vn = (vlabels != -100).sum().item()
                val_loss += voutputs.loss.item() * vn
                val_tokens += vn
        avg_val_loss = val_loss / max(val_tokens, 1)
        is_best = avg_val_loss < best_val_loss
        print0(f"     Val loss:  {avg_val_loss:.4f} {'** BEST **' if is_best else ''}")
        logger.log({"val/loss": avg_val_loss, "val/tokens": val_tokens}, step=global_step)
        if is_best:
            best_val_loss = avg_val_loss

    # ----- Save checkpoint (master only) -----
    if args.save_every_epoch and is_master:
        epoch_dir = os.path.join(args.output_dir, f"epoch_{epoch+1}")
        print0(f"\n  💾 Saving epoch {epoch+1} checkpoint...")
        maybe_empty_cache(device)
        peft_model = get_peft_model_for_save(model)
        adapter_state = build_adapter_state_dict_cpu(peft_model)
        # On Intel XPU, safetensors serialization may trigger large device->CPU
        # staging spikes and fail at save time; use PyTorch format for stability.
        peft_model.save_pretrained(
            epoch_dir,
            safe_serialization=False,
            state_dict=adapter_state if adapter_state else None,
        )
        tokenizer.save_pretrained(epoch_dir)
        meta = {
            "epoch": epoch + 1, "global_step": global_step,
            "avg_loss": avg_epoch_loss, "epoch_tokens": total_epoch_tokens,
            "config": vars(args), "distributed": use_ddp, "world_size": world_size,
        }
        with open(os.path.join(epoch_dir, "training_meta.json"), "w") as f:
            json.dump(meta, f, indent=2, default=str)
        print0(f"     ✅ Saved to {epoch_dir}")

    # Sync before next epoch
    if use_ddp:
        dist.barrier()

    print0("-" * 70)


# ---------------------------------------------------------------------------
# Save final model (master only)
# ---------------------------------------------------------------------------
total_time = time.time() - training_start_time

if is_master:
    print0("\n" + "=" * 70)
    print0("  💾 Saving final LoRA adapter...")
    final_dir = os.path.join(args.output_dir, "final")
    maybe_empty_cache(device)
    peft_model = get_peft_model_for_save(model)
    adapter_state = build_adapter_state_dict_cpu(peft_model)
    # Use non-safetensors save to reduce XPU OOM/device-lost risk at final export.
    peft_model.save_pretrained(
        final_dir,
        safe_serialization=False,
        state_dict=adapter_state if adapter_state else None,
    )
    tokenizer.save_pretrained(final_dir)
    with open(os.path.join(final_dir, "training_config.json"), "w") as f:
        json.dump(vars(args), f, indent=2, default=str)
    print0(f"  ✅ Final LoRA adapter saved to: {final_dir}")

# Log final summary
peak_mem = memory_peak_gb(device)
logger.log_summary({
    "final/total_steps": global_step,
    "final/total_tokens": total_training_tokens,
    "final/total_time_min": total_time / 60,
    "final/peak_gpu_memory_gb": peak_mem,
    "final/final_train_loss": all_epoch_losses[-1] if all_epoch_losses else 0,
    "final/world_size": world_size,
})

# Print final report
print0("\n" + "=" * 70)
print0("  📊 Training Report")
print0("=" * 70)
print0(f"  Distributed:           {'Yes (' + str(world_size) + ' devices)' if use_ddp else 'No (single device)'}")
print0(f"  Total steps:           {global_step}")
print0(f"  Total training tokens: {total_training_tokens:,} (this GPU)")
print0(f"  Total time:            {total_time/60:.1f} min")
print0(f"  Avg throughput:        {total_training_tokens/max(total_time,1)*world_size:.0f} tok/s (all GPUs)")
print0(f"  Peak GPU memory:       {peak_mem:.2f} GB")
print0(f"  OOM skipped batches:   {oom_skipped_batches}")
print0(f"  Loss progression:")
for i, loss_val in enumerate(all_epoch_losses):
    marker = " ** BEST **" if loss_val == min(all_epoch_losses) else ""
    print0(f"    Epoch {i+1}: {loss_val:.4f}{marker}")
if best_val_loss < float("inf"):
    print0(f"  Best val loss:         {best_val_loss:.4f}")
print0(f"\n  Output directory:      {args.output_dir}")
print0("=" * 70)
print0("  🎉 Training complete!")
print0("=" * 70)

logger.finish()
cleanup_distributed()
