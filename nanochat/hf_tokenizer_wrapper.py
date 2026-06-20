"""
Wrapper that adapts a HuggingFace tokenizer to provide nanochat's tokenizer interface.

This allows using any HF tokenizer (Qwen3, Llama, etc.) with nanochat's SFT data
pipeline, which expects methods like render_conversation(), encode_special(), etc.

Key design decision: we ADD nanochat's special tokens (<|bos|>, <|user_start|>, etc.)
to the HF tokenizer's vocabulary. This means:
1. The tokenizer gains all special tokens nanochat expects
2. The model's embedding layer is resized to accommodate them
3. nanochat's render_conversation logic works directly
4. The new token embeddings are learned during SFT (initialized from scratch)

Usage:
    from nanochat.hf_tokenizer_wrapper import HFTokenizerWrapper
    tokenizer = HFTokenizerWrapper("Qwen/Qwen3-0.6B")
    num_added = tokenizer.num_added_tokens  # how many tokens were added
    # Then resize model: model.resize_token_embeddings(tokenizer.get_vocab_size())
"""

import copy
import math
import torch
from functools import lru_cache
from transformers import AutoTokenizer

from nanochat.common import print0

# nanochat's special tokens (duplicated here to avoid importing nanochat.tokenizer
# which pulls in rustbpe/tiktoken that may not be installed in all environments)
NANOCHAT_SPECIAL_TOKENS = [
    "<|bos|>",
    "<|user_start|>",
    "<|user_end|>",
    "<|assistant_start|>",
    "<|assistant_end|>",
    "<|python_start|>",
    "<|python_end|>",
    "<|output_start|>",
    "<|output_end|>",
]


class HFTokenizerWrapper:
    """
    Wraps a HuggingFace tokenizer to provide the same interface as
    nanochat's RustBPETokenizer / HuggingFaceTokenizer.
    """

    def __init__(self, model_name_or_path, max_seq_len=2048):
        """
        Args:
            model_name_or_path: HuggingFace model name or local path.
            max_seq_len: maximum sequence length for render_conversation.
        """
        self.hf_tokenizer = AutoTokenizer.from_pretrained(
            model_name_or_path,
            trust_remote_code=True,
            padding_side="right",
        )
        self.max_seq_len = max_seq_len

        # Add nanochat's special tokens to the HF tokenizer
        # Only add tokens that don't already exist
        existing_tokens = set(self.hf_tokenizer.get_vocab().keys())
        tokens_to_add = [t for t in NANOCHAT_SPECIAL_TOKENS if t not in existing_tokens]
        self.num_added_tokens = 0
        if tokens_to_add:
            num_added = self.hf_tokenizer.add_special_tokens({
                'additional_special_tokens': tokens_to_add,
            })
            self.num_added_tokens = num_added
            print0(f"Added {num_added} nanochat special tokens to HF tokenizer: {tokens_to_add}")
        else:
            print0("All nanochat special tokens already exist in HF tokenizer")

        # Ensure pad_token is set
        if self.hf_tokenizer.pad_token is None:
            self.hf_tokenizer.pad_token = self.hf_tokenizer.eos_token

        print0(f"HF Tokenizer vocab size: {self.get_vocab_size()}")

    def get_vocab_size(self):
        return len(self.hf_tokenizer)

    @lru_cache(maxsize=64)
    def encode_special(self, text):
        """Encode a single special token to its token id."""
        ids = self.hf_tokenizer.convert_tokens_to_ids(text)
        if ids == self.hf_tokenizer.unk_token_id:
            # Try alternative encoding
            encoded = self.hf_tokenizer.encode(text, add_special_tokens=False)
            if len(encoded) == 1:
                return encoded[0]
            raise ValueError(f"Cannot encode special token '{text}': "
                           f"got unk_id={self.hf_tokenizer.unk_token_id}")
        return ids

    def get_bos_token_id(self):
        """Get the BOS token id. Uses nanochat's <|bos|> token."""
        return self.encode_special("<|bos|>")

    def encode(self, text, prepend=None, append=None, num_threads=None):
        """
        Encode text to token ids. Supports single string or list of strings.

        Args:
            text: string or list of strings to encode.
            prepend: special token string or token id to prepend.
            append: special token string or token id to append.
            num_threads: ignored (for API compatibility).
        """
        if isinstance(text, str):
            return self._encode_one(text, prepend=prepend, append=append)
        elif isinstance(text, list):
            return [self._encode_one(t, prepend=prepend, append=append) for t in text]
        else:
            raise ValueError(f"Invalid input type: {type(text)}")

    def _encode_one(self, text, prepend=None, append=None):
        """Encode a single string."""
        ids = self.hf_tokenizer.encode(text, add_special_tokens=False)
        if prepend is not None:
            prepend_id = prepend if isinstance(prepend, int) else self.encode_special(prepend)
            ids.insert(0, prepend_id)
        if append is not None:
            append_id = append if isinstance(append, int) else self.encode_special(append)
            ids.append(append_id)
        return ids

    def __call__(self, *args, **kwargs):
        return self.encode(*args, **kwargs)

    def decode(self, ids):
        """Decode token ids back to text."""
        return self.hf_tokenizer.decode(ids, skip_special_tokens=False)

    def id_to_token(self, token_id):
        """Convert a token id to its string representation."""
        return self.hf_tokenizer.convert_ids_to_tokens(token_id)

    def get_special_tokens(self):
        """Return the set of special token strings."""
        return set(self.hf_tokenizer.all_special_tokens)

    # -------------------------------------------------------------------------
    # Conversation rendering (same logic as nanochat's RustBPETokenizer)
    # -------------------------------------------------------------------------

    def render_conversation(self, conversation, max_tokens=None):
        """
        Tokenize a single Chat conversation.

        Returns:
        - ids: list[int] of token ids for this rendered conversation
        - mask: list[int] of same length, mask = 1 for tokens that the
                Assistant is expected to train on, 0 otherwise.
        """
        if max_tokens is None:
            max_tokens = self.max_seq_len

        ids, mask = [], []

        def add_tokens(token_ids, mask_val):
            if isinstance(token_ids, int):
                token_ids = [token_ids]
            ids.extend(token_ids)
            mask.extend([mask_val] * len(token_ids))

        # Handle system messages by merging into the first user message
        if conversation["messages"][0]["role"] == "system":
            conversation = copy.deepcopy(conversation)
            messages = conversation["messages"]
            assert messages[1]["role"] == "user", \
                "System message must be followed by a user message"
            messages[1]["content"] = messages[0]["content"] + "\n\n" + messages[1]["content"]
            messages = messages[1:]
        else:
            messages = conversation["messages"]
        assert len(messages) >= 1, f"Conversation has less than 1 message: {messages}"

        # Fetch special tokens
        bos = self.get_bos_token_id()
        user_start = self.encode_special("<|user_start|>")
        user_end = self.encode_special("<|user_end|>")
        assistant_start = self.encode_special("<|assistant_start|>")
        assistant_end = self.encode_special("<|assistant_end|>")
        python_start = self.encode_special("<|python_start|>")
        python_end = self.encode_special("<|python_end|>")
        output_start = self.encode_special("<|output_start|>")
        output_end = self.encode_special("<|output_end|>")

        # Render the conversation
        add_tokens(bos, 0)
        for i, message in enumerate(messages):
            must_be_from = "user" if i % 2 == 0 else "assistant"
            assert message["role"] == must_be_from, \
                f"Message {i} is from {message['role']} but should be from {must_be_from}"

            content = message["content"]

            if message["role"] == "user":
                assert isinstance(content, str), "User messages must be strings"
                value_ids = self.encode(content)
                add_tokens(user_start, 0)
                add_tokens(value_ids, 0)
                add_tokens(user_end, 0)
            elif message["role"] == "assistant":
                add_tokens(assistant_start, 0)
                if isinstance(content, str):
                    value_ids = self.encode(content)
                    add_tokens(value_ids, 1)
                elif isinstance(content, list):
                    for part in content:
                        value_ids = self.encode(part["text"])
                        if part["type"] == "text":
                            add_tokens(value_ids, 1)
                        elif part["type"] == "python":
                            add_tokens(python_start, 1)
                            add_tokens(value_ids, 1)
                            add_tokens(python_end, 1)
                        elif part["type"] == "python_output":
                            add_tokens(output_start, 0)
                            add_tokens(value_ids, 0)
                            add_tokens(output_end, 0)
                        else:
                            raise ValueError(f"Unknown part type: {part['type']}")
                else:
                    raise ValueError(f"Unknown content type: {type(content)}")
                add_tokens(assistant_end, 1)

        # Truncate
        ids = ids[:max_tokens]
        mask = mask[:max_tokens]
        return ids, mask

    def render_for_completion(self, conversation):
        """
        Render a conversation for RL completion (priming assistant for response).
        """
        conversation = copy.deepcopy(conversation)
        messages = conversation["messages"]
        assert messages[-1]["role"] == "assistant", \
            "Last message must be from the Assistant"
        messages.pop()
        ids, mask = self.render_conversation(conversation)
        assistant_start = self.encode_special("<|assistant_start|>")
        ids.append(assistant_start)
        return ids

    def visualize_tokenization(self, ids, mask, with_token_id=False):
        """Visualize tokenization with colors (for debugging)."""
        RED = '\033[91m'
        GREEN = '\033[92m'
        RESET = '\033[0m'
        GRAY = '\033[90m'
        tokens = []
        for token_id, mask_val in zip(ids, mask):
            token_str = self.decode([token_id])
            color = GREEN if mask_val == 1 else RED
            tokens.append(f"{color}{token_str}{RESET}")
            if with_token_id:
                tokens.append(f"{GRAY}({token_id}){RESET}")
        return '|'.join(tokens)

    # -------------------------------------------------------------------------
    # Token bytes computation (for BPB evaluation)
    # -------------------------------------------------------------------------

    def compute_token_bytes(self, device="cpu"):
        """
        Compute the number of UTF-8 bytes for each token in the vocabulary.

        Returns a 1D tensor of shape (vocab_size,) where token_bytes[i] is
        the number of UTF-8 bytes for token i. Special tokens get 0 bytes
        (they are excluded from BPB computation).
        """
        vocab_size = self.get_vocab_size()
        token_bytes = torch.zeros(vocab_size, dtype=torch.float32, device=device)

        special_ids = set()
        for st in NANOCHAT_SPECIAL_TOKENS:
            try:
                sid = self.encode_special(st)
                special_ids.add(sid)
            except (ValueError, KeyError):
                pass

        # Also mark the HF tokenizer's own special tokens
        for st in self.hf_tokenizer.all_special_tokens:
            sid = self.hf_tokenizer.convert_tokens_to_ids(st)
            if sid is not None:
                special_ids.add(sid)

        for i in range(vocab_size):
            if i in special_ids:
                token_bytes[i] = 0  # special tokens don't count
                continue
            try:
                decoded = self.hf_tokenizer.decode([i], skip_special_tokens=False)
                n_bytes = len(decoded.encode('utf-8'))
                token_bytes[i] = float(n_bytes)
            except Exception:
                token_bytes[i] = 1.0  # fallback

        return token_bytes

    def save(self, output_dir):
        """Save the tokenizer (including added special tokens) to disk."""
        self.hf_tokenizer.save_pretrained(output_dir)
        print0(f"Saved HF tokenizer to {output_dir}")

