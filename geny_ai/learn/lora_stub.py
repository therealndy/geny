"""Small LoRA/PEFT example stub explaining how to fine-tune a model with PEFT.

This file is intentionally non-executable as-is on CPU-only environments; it's
an example script and pointer to commands for users with GPU resources.
"""

EXAMPLE = {
    "description": "Use PEFT/LoRA for efficient fine-tuning",
    "pip": "pip install peft accelerate transformers datasets",
    "snippet": """
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import get_peft_model, LoraConfig, TaskType

model_name = 'gpt2'
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, device_map='auto')

lora_config = LoraConfig(
    r=8,
    lora_alpha=32,
    target_modules=["c_attn"],
    bias="none",
    task_type=TaskType.CAUSAL_LM,
)
peft_model = get_peft_model(model, lora_config)

# continue with Trainer or Accelerate-based training loop
""",
}
