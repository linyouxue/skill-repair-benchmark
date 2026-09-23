"""Skill bundle package marker.

This file makes the top-level `skills` directory importable when individual
scripts are executed directly (e.g. `python3 skills/<skill>/scripts/<script>.py`).

The benchmark runtime does not guarantee installing this repository as a Python
package, so we rely on Python's default behavior of adding the current working
directory to `sys.path`.
"""
