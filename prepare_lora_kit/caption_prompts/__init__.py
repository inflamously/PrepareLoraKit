"""Global, reusable caption prompt library shared across all projects."""
from .registry import CaptionPrompt, KINDS, delete, list_prompts, load, save

__all__ = ["CaptionPrompt", "KINDS", "delete", "list_prompts", "load", "save"]
