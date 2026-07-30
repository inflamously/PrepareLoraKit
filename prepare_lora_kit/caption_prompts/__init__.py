"""Global, reusable caption prompt library shared across all projects."""
from .prompt_registry import KINDS, CaptionPrompt, delete, list_prompts, load, save

__all__ = ["KINDS", "CaptionPrompt", "delete", "list_prompts", "load", "save"]
