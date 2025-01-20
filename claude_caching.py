"""
title: Claude Caching
author: jojje
author_url: https://github.com/jojje
funding_url: https://github.com/open-webui
version: 0.1.1
"""

# This script provides prompt prefix caching for Anthropic Claude models.
#
# Four things for users to be aware of regarding Anthropic's caching:
# 1. Cache hits are 90% cheaper than processing the input.
# 2. Cache misses cost 25% more than for prompt processing.
# 3. The output price is the same regardless if caching is used or not.
# 4. Antropic only caches prompts that exceed 1024 tokens for Sonnet, and 2048 for Heiku,
#    which means users who are concerned about the 25% prompt processing bump for small
#    prompts need not worry. Anthropic treats small prompts as uncached ones.
#
# To know about this script:
# * When enabled (for a given model, or globally) it only engages when an anthropic claude model is used.
# * If you want to check or debug the cache decorated prompt, there is a debug toggle in the function's settings
#   which when enabled logs each prompt to the webui console.
# * The cache statistics that Anthropic sends back with each response are unfortunately unavailable to this
#   function, since webui (unfortunately) prunes that information before the function has a chance to see it.
# * The home for this function is at: https://github.com/jojje/openwebui-claude-caching

from pydantic import BaseModel, Field
from typing import Optional, List

NAME = "claude-cache"


def clear_cache_markers(messages: List[dict]):
    # just in case webui don't provide us clean message copies on each send
    for m in messages:
        if isinstance(m["content"], list):
            for entry in m["content"]:
                if "cache_control" in entry:
                    del entry["cache_control"]


def cache_message(message: dict):
    content = message["content"]
    if isinstance(content, str):  # normalize content format
        content = [{"type": "text", "text": content}]

    content[-1]["cache_control"] = {"type": "ephemeral"}
    message["content"] = content


def cache_system_prompt(messages: List[dict]):
    sys_messages = [m for m in messages if m["role"] == "system"]
    for m in reversed(sys_messages):
        cache_message(m)
        return


def cache_dialog_messages(messages: List[dict]):
    # cache the entire range of user-assistant pairs, allowing for
    # "regenerate" of the last assistant message to also benefit from caching.
    tail = [m for m in messages if m["role"] in ("user", "assistant")][-2:]
    for m in tail:
        cache_message(m)


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Filter processing priority level")
        debug: bool = Field(
            default=False, description="Log the filter modified conversation to console"
        )

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        if not self._is_applicable(__user__, body):
            return body

        messages = body.get("messages", [])
        clear_cache_markers(messages)
        cache_system_prompt(messages)
        cache_dialog_messages(messages)
        self._debug("body:", body)

        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body

    def _is_applicable(self, user: dict, body: dict) -> bool:
        model = body.get("model", "")
        return user.get("role", "admin") in ["user", "admin"] and model.startswith(
            "anthropic.claude"
        )

    def _debug(self, *args):
        if self.valves.debug:
            print(f"[{NAME}]", *args)
