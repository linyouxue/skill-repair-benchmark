import json
import re
from typing import List, Dict, Any


def parse_json_object(text: str) -> Dict[str, Any]:
    r"""Parse a model-supplied JSON object without accepting plain text.

    Structured model fields sometimes contain an extra backslash when shell
    syntax such as ``\(`` is embedded inside a JSON string.  The generic
    ``convert_text_to_jsonl`` helper deliberately falls back to a text wrapper,
    which is useful for free-form responses but unsafe for executable tool
    arguments.  This stricter helper repairs only invalid JSON escape runs and
    otherwise fails closed.
    """

    parsed = convert_text_to_jsonl(text)
    if parsed and isinstance(parsed[0], dict):
        candidate = parsed[0]
        if not (candidate.get("mode") == "text" and set(candidate) == {"mode", "text"}):
            return candidate

    repaired = _repair_invalid_json_escape_runs(text.strip())
    try:
        candidate = json.loads(repaired)
    except json.JSONDecodeError as exc:
        raise ValueError("tool arguments are not a valid JSON object") from exc
    if not isinstance(candidate, dict):
        raise ValueError("tool arguments must decode to a JSON object")
    return candidate


def _repair_invalid_json_escape_runs(text: str) -> str:
    r"""Normalize odd backslash runs before non-JSON escape characters.

    A shell grouping token should be encoded as ``\\\\(`` in JSON.  Some
    structured responses contain three backslashes instead, leaving the last
    one as the invalid JSON escape ``\(``.  Reducing a longer odd run by one
    preserves the intended decoded shell backslash.  A lone invalid backslash
    is doubled for the same reason.
    """

    valid_escape_starts = set('"\\/bfnrtu')
    output: List[str] = []
    index = 0
    while index < len(text):
        if text[index] != "\\":
            output.append(text[index])
            index += 1
            continue
        end = index
        while end < len(text) and text[end] == "\\":
            end += 1
        count = end - index
        next_character = text[end] if end < len(text) else ""
        if count % 2 == 1 and next_character not in valid_escape_starts:
            count = count + 1 if count == 1 else count - 1
        output.append("\\" * count)
        index = end
    return "".join(output)

def convert_text_to_jsonl(text: str) -> List[Dict[str, Any]]:
    """
    Convert text output from model to JSONL format.
    Handles various formats the model might output:
    - Raw JSON array
    - JSON wrapped in markdown code blocks
    - JSONL format (one JSON object per line)
    - Mixed text with JSON content
    """
    if not text or not text.strip():
        return []
    
    cleaned_text = text.strip()
    
    strategies = [
        ("markdown_json", _parse_markdown_json),
        ("json_array", _parse_json_array),
        ("jsonl_lines", _parse_jsonl_lines),
        ("mixed_content", _parse_mixed_content),
        ("single_json_objects", _parse_single_json_objects),
        ("text", _parse_text_to_json)
    ]
    
    for _, strategy_func in strategies:
        try:
            result = strategy_func(cleaned_text)
            if result:
                return result
        except Exception as e:
            continue
    print(f"Failed to parse text: {text}")
    return []


def _parse_markdown_json(text: str) -> List[Dict[str, Any]]:
    """Parse JSON wrapped in markdown code blocks"""
    # Look for ```json ... ``` or ``` ... ``` patterns
    json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(json_pattern, text, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        try:
            data = json.loads(match.strip())
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            continue
    
    raise ValueError()


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    """Parse direct JSON array"""
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            raise ValueError
    except json.JSONDecodeError:
        raise ValueError()


def _parse_jsonl_lines(text: str) -> List[Dict[str, Any]]:
    """Parse JSONL format (one JSON object per line)"""
    lines = text.strip().split('\n')
    results = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        try:
            data = json.loads(line)
            results.append(data)
        except json.JSONDecodeError:
            pass
    
    if results:
        return results
    else:
        raise ValueError()


def _parse_mixed_content(text: str) -> List[Dict[str, Any]]:
    """Parse mixed content by extracting JSON objects"""
    json_objects = []
    
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    potential_jsons = re.findall(json_pattern, text, re.DOTALL)
    
    for potential_json in potential_jsons:
        try:
            data = json.loads(potential_json)
            if isinstance(data, dict):
                json_objects.append(data)
        except json.JSONDecodeError:
            continue
    
    if json_objects:
        return json_objects
    else:
        raise ValueError()


def _parse_single_json_objects(text: str) -> List[Dict[str, Any]]:
    """Parse individual JSON objects separated by newlines or other delimiters"""
    delimiters = ['\n\n', '\n---\n', '\n***\n', '\n---', '\n***']
    
    for delimiter in delimiters:
        parts = text.split(delimiter)
        results = []
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            try:
                data = json.loads(part)
                if isinstance(data, dict):
                    results.append(data)
                elif isinstance(data, list):
                    results.extend(data)
            except json.JSONDecodeError:
                continue
        
        if results:
            return results
    raise ValueError()
def _parse_text_to_json(text: str) -> List[Dict[str, Any]]:
       return [{"mode": "text", "text": text}]
