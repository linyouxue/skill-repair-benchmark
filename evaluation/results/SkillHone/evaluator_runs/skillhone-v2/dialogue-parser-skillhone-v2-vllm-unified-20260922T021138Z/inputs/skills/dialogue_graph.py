"""Public import shim for the Dialogue Graph skill.

The SkillHone prompt and SKILL.md advertise `from dialogue_graph import Graph, Node, Edge`.
The original implementation lives in `scripts/dialogue_graph.py`.

This shim preserves the documented import path without changing the existing code.
"""

from scripts.dialogue_graph import Edge, Graph, Node

__all__ = ["Graph", "Node", "Edge"]
