"""
Custom JSONL Task for GRPO training.

Loads a local JSONL file where each line has:
  - "messages": list of chat messages
  - "answer": ground truth answer string

Reward: 1.0 if model output contains the correct answer in GSM8K format.
"""

import os
import re
import json

from nanochat.common import print0

_GSM_RE = re.compile(r"####\s*(\-?[0-9\.\,]+)")


class CustomRLTask:
    """RL task from a local JSONL file."""

    def __init__(self, filepath):
        assert os.path.exists(filepath), f"File not found: {filepath}"
        self.data = []
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                assert "messages" in obj and "answer" in obj
                self.data.append(obj)
        print0(f"Loaded {len(self.data)} examples from {filepath}")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]

    def reward(self, item, assistant_response):
        """
        Reward: 1.0 if the correct answer appears in the response.
        Checks: #### N, "the answer is N", \\boxed{N}
        """
        gt = str(item["answer"]).replace(",", "").strip()

        # Format 1: #### <number>
        match = _GSM_RE.search(assistant_response)
        if match:
            pred = match.group(1).replace(",", "").strip()
            if pred == gt:
                return 1.0

        # Format 2: "the answer is <number>"
        m2 = re.search(
            r"(?:the\s+)?(?:final\s+)?answer\s+is\s*:?\s*\$?(\-?[0-9\.\,]+)",
            assistant_response, re.IGNORECASE)
        if m2:
            pred = m2.group(1).replace(",", "").replace("$", "").strip()
            if pred == gt:
                return 1.0

        # Format 3: \\boxed{<number>}
        m3 = re.search(r"\\boxed\{(\-?[0-9\.\,]+)\}", assistant_response)
        if m3:
            pred = m3.group(1).replace(",", "").strip()
            if pred == gt:
                return 1.0

        return 0.0

    def evaluate(self, item, assistant_response):
        return int(self.reward(item, assistant_response))

