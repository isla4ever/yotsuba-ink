"""
Wrapper that adapts HuggingFace CausalLM models (e.g. Qwen3, Llama, Mistral)
to nanochat's GPT interface. This allows using any HF model with nanochat's
training infrastructure (SFT data pipeline, distributed training, etc.)

Usage:
    from nanochat.hf_model_wrapper import HFModelWrapper
    model = HFModelWrapper("Qwen/Qwen3-0.6B", device=device)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.distributed as dist
from dataclasses import dataclass
from contextlib import contextmanager

from transformers import AutoModelForCausalLM, AutoConfig
from nanochat.common import get_dist_info, print0


@dataclass
class HFModelConfig:
    """Mirrors nanochat's GPTConfig but derived from a HuggingFace model config."""
    sequence_len: int = 2048
    vocab_size: int = 32768
    n_layer: int = 12
    n_head: int = 12
    n_kv_head: int = 12
    n_embd: int = 768
    window_pattern: str = "L"


class DistAdamW(torch.optim.AdamW):
    """
    AdamW with gradient all-reduce for distributed training.

    In nanochat's architecture, gradient synchronization is handled by the optimizer
    (not by DDP). This class follows the same pattern: it performs an async all-reduce
    on gradients before the standard AdamW parameter update step.
    """

    @torch.no_grad()
    def step(self, closure=None):
        # Phase 1: Launch async all-reduce on all gradients
        handles = []
        for group in self.param_groups:
            for p in group['params']:
                if p.grad is not None:
                    handle = dist.all_reduce(p.grad, op=dist.ReduceOp.AVG, async_op=True)
                    handles.append(handle)
        # Phase 2: Wait for all communication to finish
        for h in handles:
            h.wait()
        # Phase 3: Standard AdamW update
        return super().step(closure)


class HFModelWrapper(nn.Module):
    """
    Wraps a HuggingFace CausalLM model to provide nanochat's GPT interface.

    Key interface methods expected by nanochat's training scripts:
    - forward(idx, targets) -> loss (scalar) or logits
    - forward(idx, targets, loss_reduction='none') -> per-token losses
    - setup_optimizer(...) -> optimizer with param_groups having 'kind' and 'initial_lr'
    - estimate_flops() -> int
    - num_scaling_params() -> dict
    - get_device() -> torch.device
    - config.n_layer, config.n_head, config.n_embd, config.vocab_size, etc.
    """

    def __init__(self, model_name_or_path, device, dtype=torch.bfloat16,
                 sequence_len=2048, extra_special_tokens=None):
        """
        Args:
            model_name_or_path: HuggingFace model name (e.g. "Qwen/Qwen3-0.6B")
                                or local path to a saved model.
            device: torch.device to place the model on.
            dtype: torch.dtype for model weights (default: bfloat16).
            sequence_len: max sequence length for training.
            extra_special_tokens: list of special token strings to add to the model's
                                  vocabulary (e.g. nanochat's special tokens).
        """
        super().__init__()

        print0(f"Loading HuggingFace model: {model_name_or_path}")

        # Load the HF model
        self.hf_model = AutoModelForCausalLM.from_pretrained(
            model_name_or_path,
            dtype=dtype,
            trust_remote_code=True,
        )

        # If extra special tokens are provided, check if we need to resize embeddings.
        # Many models (e.g. Qwen3) have config.vocab_size > len(tokenizer), meaning
        # the embedding table has room for extra tokens already.
        self._original_vocab_size = self.hf_model.config.vocab_size
        current_embedding_size = self.hf_model.get_input_embeddings().weight.shape[0]
        if extra_special_tokens:
            # Only resize if the tokenizer's vocab exceeds the current embedding table
            # We pass the desired tokenizer_vocab_size separately
            pass  # Resizing is handled below via set_tokenizer_vocab_size()

        # Move to device
        self.hf_model.to(device)

        # Build nanochat-compatible config
        hf_config = self.hf_model.config
        self.config = HFModelConfig(
            sequence_len=sequence_len,
            vocab_size=current_embedding_size,  # use actual embedding size
            n_layer=hf_config.num_hidden_layers,
            n_head=hf_config.num_attention_heads,
            n_kv_head=getattr(hf_config, 'num_key_value_heads', hf_config.num_attention_heads),
            n_embd=hf_config.hidden_size,
            window_pattern="L",  # External models typically use full attention
        )

        print0(f"Model config: layers={self.config.n_layer}, "
               f"heads={self.config.n_head}, kv_heads={self.config.n_kv_head}, "
               f"dim={self.config.n_embd}, vocab={self.config.vocab_size}")

        # Store some info
        self._model_name = model_name_or_path
        self._dtype = dtype

    def sync_vocab_size(self, tokenizer_vocab_size):
        """
        Ensure model embedding size matches tokenizer vocab size.
        If the tokenizer has more tokens than the model's embedding table,
        resize the embeddings to accommodate them.
        If the model already has enough room, do nothing (the extra rows
        in the embedding table are harmless).
        """
        current_size = self.hf_model.get_input_embeddings().weight.shape[0]
        if tokenizer_vocab_size > current_size:
            self.hf_model.resize_token_embeddings(tokenizer_vocab_size)
            self.config.vocab_size = tokenizer_vocab_size
            print0(f"Resized embeddings: {current_size} -> {tokenizer_vocab_size}")
        elif tokenizer_vocab_size < current_size:
            print0(f"Model embedding ({current_size}) already covers tokenizer vocab ({tokenizer_vocab_size}), no resize needed")
        else:
            print0(f"Model embedding and tokenizer vocab sizes match: {current_size}")

    def forward(self, idx, targets=None, kv_cache=None, loss_reduction='mean'):
        """
        Match nanochat's GPT.forward signature.

        IMPORTANT: nanochat's data pipeline already shifts inputs/targets, i.e.:
            inputs  = tokens[:, :-1]
            targets = tokens[:, 1:]
        So we must NOT use HuggingFace's built-in loss (which shifts again).
        Instead, we compute the loss manually.

        Args:
            idx: input token ids, shape (B, T), dtype int32 or int64
            targets: target token ids, shape (B, T), dtype int64. -1 = ignore.
            kv_cache: ignored (not supported for HF models in this wrapper)
            loss_reduction: 'mean' (scalar loss) or 'none' (per-token losses)

        Returns:
            If targets is None: logits of shape (B, T, vocab_size)
            If targets is not None and loss_reduction='mean': scalar loss
            If targets is not None and loss_reduction='none': per-token losses (B*T,)
        """
        input_ids = idx.long()  # HF models expect int64
        outputs = self.hf_model(input_ids=input_ids)
        logits = outputs.logits  # (B, T, vocab_size)

        if targets is not None:
            # Compute loss manually (nanochat already shifts inputs/targets)
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.reshape(-1),
                ignore_index=-1,
                reduction=loss_reduction,
            )
            return loss
        else:
            return logits

    def setup_optimizer(self, lr=2e-5, weight_decay=0.01,
                        embedding_lr=None, unembedding_lr=None,
                        matrix_lr=None, scalar_lr=None,
                        adam_betas=(0.9, 0.999), **kwargs):
        """
        Setup optimizer for SFT training.

        Uses AdamW (or DistAdamW for distributed training) with standard
        parameter grouping: decay vs no-decay.

        All param_groups have a 'kind' field set to 'adamw' for compatibility
        with nanochat's training loop which checks group['kind'].

        The lr arguments (embedding_lr, unembedding_lr, matrix_lr) are accepted
        for API compatibility with nanochat's GPT.setup_optimizer() but are
        mapped to a single LR for simplicity.
        """
        ddp, rank, local_rank, world_size = get_dist_info()

        # Use matrix_lr as the base LR if provided, otherwise use lr
        base_lr = matrix_lr if matrix_lr is not None else lr
        embed_lr = embedding_lr if embedding_lr is not None else base_lr

        # Separate parameters into groups
        decay_params = []
        no_decay_params = []
        embedding_params = []

        for name, param in self.hf_model.named_parameters():
            if not param.requires_grad:
                continue
            if 'embed' in name:
                embedding_params.append(param)
            elif param.ndim < 2 or 'norm' in name or 'bias' in name:
                no_decay_params.append(param)
            else:
                decay_params.append(param)

        param_groups = [
            {
                'kind': 'adamw',
                'params': decay_params,
                'lr': base_lr,
                'betas': adam_betas,
                'eps': 1e-8,
                'weight_decay': weight_decay,
            },
            {
                'kind': 'adamw',
                'params': no_decay_params,
                'lr': base_lr,
                'betas': adam_betas,
                'eps': 1e-8,
                'weight_decay': 0.0,
            },
            {
                'kind': 'adamw',
                'params': embedding_params,
                'lr': embed_lr,
                'betas': adam_betas,
                'eps': 1e-8,
                'weight_decay': 0.0,
            },
        ]

        # Filter out empty groups
        param_groups = [g for g in param_groups if len(g['params']) > 0]

        # Use DistAdamW for distributed training, standard AdamW otherwise
        Factory = DistAdamW if ddp else torch.optim.AdamW
        optimizer = Factory(param_groups)

        # Set initial_lr for LR scheduling (nanochat convention)
        for group in optimizer.param_groups:
            group['initial_lr'] = group['lr']

        n_decay = sum(p.numel() for p in decay_params)
        n_no_decay = sum(p.numel() for p in no_decay_params)
        n_embed = sum(p.numel() for p in embedding_params)
        print0(f"Optimizer groups: decay={n_decay:,} params, "
               f"no_decay={n_no_decay:,} params, "
               f"embedding={n_embed:,} params")

        return optimizer

    def estimate_flops(self):
        """
        Estimate FLOPs per token (forward + backward).
        Rough estimate: 6 * num_params (standard approximation).
        """
        nparams = sum(p.numel() for p in self.parameters())
        # Exclude embedding parameters (they are lookups, not matmuls)
        embed_params = self.hf_model.get_input_embeddings().weight.numel()
        matmul_params = nparams - embed_params
        # 6N approximation: 2 FLOPs per param in forward, 4 in backward
        h = self.config.n_head
        d = self.config.n_embd // self.config.n_head
        t = self.config.sequence_len
        # Attention FLOPs (key @ query)
        attn_flops = 12 * h * d * t * self.config.n_layer
        return 6 * matmul_params + attn_flops

    def num_scaling_params(self):
        """Return parameter counts for compatibility with nanochat."""
        total = sum(p.numel() for p in self.parameters())
        embed = self.hf_model.get_input_embeddings().weight.numel()
        return {
            'total': total,
            'transformer_matrices': total - embed,
            'lm_head': self.hf_model.get_output_embeddings().weight.numel() if self.hf_model.get_output_embeddings() is not None else 0,
            'wte': embed,
            'value_embeds': 0,
            'scalars': 0,
        }

    def get_device(self):
        """Return the device the model is on."""
        return next(self.parameters()).device

    @torch.no_grad()
    def generate(self, input_ids, max_new_tokens=256, temperature=1.0,
                 top_k=None, do_sample=True, pad_token_id=None,
                 eos_token_id=None, num_return_sequences=1, **kwargs):
        """
        Generate completions using HuggingFace's native generate().

        Args:
            input_ids: (B, T) tensor of input token ids, or (T,) for unbatched.
            max_new_tokens: maximum number of new tokens to generate.
            temperature: sampling temperature (0 = greedy).
            top_k: top-k sampling (None = disabled).
            do_sample: whether to sample (vs greedy).
            pad_token_id: pad token id for batched generation.
            eos_token_id: stop token id(s).
            num_return_sequences: number of completions per input.

        Returns:
            output_ids: (B * num_return_sequences, T + generated_len) tensor.
        """
        was_training = self.hf_model.training
        self.hf_model.eval()

        if input_ids.dim() == 1:
            input_ids = input_ids.unsqueeze(0)

        gen_kwargs = dict(
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            num_return_sequences=num_return_sequences,
        )
        if do_sample and temperature > 0:
            gen_kwargs['temperature'] = temperature
        if top_k is not None and top_k > 0:
            gen_kwargs['top_k'] = top_k
        if pad_token_id is not None:
            gen_kwargs['pad_token_id'] = pad_token_id
        if eos_token_id is not None:
            gen_kwargs['eos_token_id'] = eos_token_id

        output_ids = self.hf_model.generate(input_ids, **gen_kwargs, **kwargs)

        if was_training:
            self.hf_model.train()

        return output_ids

    # ------------------------------------------------------------------
    # LoRA support (via PEFT)
    # ------------------------------------------------------------------

    def apply_lora(self, r=16, alpha=None, lora_alpha=None, dropout=0.05,
                   target_modules=None, lora_dropout=None):
        """
        Apply LoRA adapter to the model using PEFT.

        Args:
            r: LoRA rank (default 16).
            alpha / lora_alpha: LoRA scaling factor (accepts both names for
                compatibility; lora_alpha takes precedence).
            dropout / lora_dropout: dropout for LoRA layers (lora_dropout
                takes precedence).
            target_modules: list of module name patterns to apply LoRA to.
                Default targets common Qwen/Llama projection layers.
        """
        from peft import LoraConfig, get_peft_model, TaskType

        # Resolve parameter aliases
        resolved_alpha = lora_alpha if lora_alpha is not None else (alpha if alpha is not None else r * 2)
        resolved_dropout = lora_dropout if lora_dropout is not None else dropout

        if target_modules is None:
            target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                              "gate_proj", "up_proj", "down_proj"]

        lora_config = LoraConfig(
            r=r,
            lora_alpha=resolved_alpha,
            lora_dropout=resolved_dropout,
            target_modules=target_modules,
            task_type=TaskType.CAUSAL_LM,
            bias="none",
        )

        self.hf_model = get_peft_model(self.hf_model, lora_config)
        self._has_lora = True

        # Report stats
        trainable = sum(p.numel() for p in self.hf_model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in self.hf_model.parameters())
        pct = trainable / total * 100
        print0(f"LoRA applied: {trainable:,} trainable / {total:,} total ({pct:.2f}%)")

    @contextmanager
    def disable_lora(self):
        """
        Context manager that temporarily disables the LoRA adapter, making
        the model behave like the original base model.  Useful for computing
        reference log-probs without extra GPU memory.
        """
        if not getattr(self, '_has_lora', False):
            yield
            return

        self.hf_model.disable_adapter_layers()
        try:
            yield
        finally:
            self.hf_model.enable_adapter_layers()

    def save_hf(self, output_dir):
        """
        Save the model in HuggingFace format.
        If LoRA is active, saves only the adapter weights (much smaller).
        Otherwise saves the full model.
        """
        print0(f"Saving HuggingFace model to {output_dir}")
        if getattr(self, '_has_lora', False):
            self.hf_model.save_pretrained(output_dir)
            print0(f"Saved LoRA adapter to {output_dir}")
        else:
            self.hf_model.save_pretrained(output_dir)

