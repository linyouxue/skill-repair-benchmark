"""Tiny ACP terminal agent for SkillsBench/OpenRouter integration smoke tests.

The process runs inside the benchmark container. It intentionally exposes one
tool (``run_shell``), emits every command as an ACP tool-call title, and lets
SkillsBench's original verifier decide success. It is not a replacement for a
full coding agent; its purpose is to remove JS-agent installation as a confound
while validating trajectory capture and file-resource graph construction.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import signal
import ssl
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import base64
import zipfile
import zlib
from typing import Any


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MAX_TOOL_ROUNDS = 24
MAX_TOOL_ROUNDS = max(
    1,
    int(
        os.environ.get(
            "CAUSALFLOW_OPENROUTER_MAX_TOOL_ROUNDS", str(DEFAULT_MAX_TOOL_ROUNDS)
        )
    ),
)
MAX_TOOL_OUTPUT = 20_000
MAX_SKILL_CONTEXT = 60_000
DEFAULT_MAX_COMPLETION_TOKENS = 2_048
RESOURCE_EVENT_PREFIX = "CAUSALFLOW_RESOURCE_EVENT="
SNAPSHOT_IGNORE_NAMES = {
    ".git",
    ".next",
    ".pytest_cache",
    "__pycache__",
    ".DS_Store",
}
VOLATILE_JSON_KEYS = {"CreatedAt", "GeneratedAt", "ReportID"}
PYTHON_AUDIT_DIR = "/tmp/causalflow-python-audit"
PYTHON_AUDIT_SOURCE = r"""import json
import os
import sys

_base = os.path.realpath(os.environ.get("CAUSALFLOW_AUDIT_ROOT", os.getcwd()))
_log = os.environ.get("CAUSALFLOW_AUDIT_LOG", "")
_busy = False


def _audit(event, args):
    global _busy
    if _busy or event != "open" or not _log or not args:
        return
    try:
        raw_path = os.fspath(args[0])
    except TypeError:
        return
    if not isinstance(raw_path, str):
        return
    path = os.path.realpath(raw_path)
    if path != _base and not path.startswith(_base.rstrip("/") + "/"):
        return
    mode = args[1] if len(args) > 1 else "r"
    if isinstance(mode, int):
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        operation = "write" if mode & write_flags else "read"
    else:
        operation = "write" if any(flag in str(mode) for flag in "wax+") else "read"
    record = {"path": os.path.relpath(path, _base).replace(os.sep, "/"), "operation": operation}
    try:
        _busy = True
        fd = os.open(_log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (json.dumps(record, separators=(",", ":")) + "\n").encode())
        finally:
            os.close(fd)
    except OSError:
        pass
    finally:
        _busy = False


sys.addaudithook(_audit)
"""


def describe_openrouter_http_error(exc: urllib.error.HTTPError) -> str:
    """Return useful OpenRouter diagnostics without echoing request secrets."""

    try:
        raw_body = exc.read().decode("utf-8", errors="replace")
    except OSError:
        raw_body = ""
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        payload = {}

    details = [f"OpenRouter HTTP {exc.code}"]
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        for field in ("code", "type", "message"):
            value = error.get(field)
            if value not in (None, ""):
                details.append(f"{field}={value}")
    elif raw_body:
        details.append(f"body={raw_body[:500]}")

    metadata = (
        payload.get("openrouter_metadata") if isinstance(payload, dict) else None
    )
    if isinstance(metadata, dict):
        pipeline = metadata.get("pipeline")
        if isinstance(pipeline, list):
            stages = []
            for stage in pipeline:
                if not isinstance(stage, dict):
                    continue
                name = stage.get("name") or stage.get("type") or "unknown"
                status = stage.get("status") or stage.get("result") or "unknown"
                stages.append(f"{name}:{status}")
            if stages:
                details.append("pipeline=" + ",".join(stages))
    return "; ".join(details)


def send(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def recv() -> dict[str, Any]:
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    payload = json.loads(line)
    return payload if isinstance(payload, dict) else {}


def emit_text(session_id: str, text: str) -> None:
    send(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": text},
                },
            },
        }
    )


def emit_tool_call(
    session_id: str,
    call_id: str,
    command: str,
    *,
    kind: str = "execute",
) -> None:
    # BenchFlow 0.6.3 does not preserve ACP structured input in ATIF, while
    # titles are intended for short display text.  Emit a compact title and a
    # lossless command marker in the tool result instead of silently treating
    # a truncated title as replayable code.
    title = command if len(command) <= 4000 else command[:3960] + "\n...[truncated]"
    send(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "tool_call",
                    "toolCallId": call_id,
                    # BenchFlow 0.6.3 drops ACP structured input from ATIF. Put
                    # the actual command in title so the conservative adapter
                    # can recover it while labelling the source title_fallback.
                    "title": title,
                    "kind": kind,
                    "status": "in_progress",
                    "input": json.dumps({"command": command}),
                },
            },
        }
    )


def emit_tool_result(
    session_id: str,
    call_id: str,
    result: str,
    *,
    succeeded: bool,
) -> None:
    send(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "tool_call_update",
                    "toolCallId": call_id,
                    "status": "completed" if succeeded else "failed",
                    "content": [
                        {
                            "type": "content",
                            "content": {
                                "type": "text",
                                "text": result[-MAX_TOOL_OUTPUT:],
                            },
                        }
                    ],
                },
            },
        }
    )


def openrouter_chat(model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required")
    raw_max_tokens = os.environ.get(
        "CAUSALFLOW_OPENROUTER_MAX_TOKENS",
        str(DEFAULT_MAX_COMPLETION_TOKENS),
    )
    try:
        max_tokens = int(raw_max_tokens)
    except ValueError as exc:
        raise RuntimeError(
            "CAUSALFLOW_OPENROUTER_MAX_TOKENS must be a positive integer"
        ) from exc
    if max_tokens < 1:
        raise RuntimeError(
            "CAUSALFLOW_OPENROUTER_MAX_TOKENS must be a positive integer"
        )
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "usage": {"include": True},
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "run_shell",
                    "description": (
                        "Run a shell command inside the isolated benchmark container. "
                        "Use it to inspect files, create or edit outputs, and test work."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "Exact bash command to execute",
                            }
                        },
                        "required": ["command"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "tool_choice": "auto",
    }
    request_data = json.dumps(payload).encode("utf-8")
    retryable_transport_errors = (
        urllib.error.URLError,
        TimeoutError,
        http.client.IncompleteRead,
        http.client.RemoteDisconnected,
        ssl.SSLError,
        ConnectionResetError,
        BrokenPipeError,
    )
    last_transport_error: BaseException | None = None
    for attempt in range(5):
        # Rebuild the request after a partial HTTP response; reusing it proved
        # unreliable during transient proxy failures in long benchmark runs.
        request = urllib.request.Request(
            OPENROUTER_URL,
            data=request_data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/benchflow-ai/skillsbench",
                "X-Title": "CausalFlow SkillsBench smoke",
                "X-OpenRouter-Metadata": "enabled",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw_body = response.read().decode("utf-8")
            body = json.loads(raw_body)
            if not isinstance(body, dict):
                raise RuntimeError("OpenRouter returned a non-object response")
            error = body.get("error")
            if isinstance(error, dict):
                code = error.get("code")
                if attempt < 4 and code in {408, 409, 429, 500, 502, 503, 504}:
                    time.sleep(min(2 ** (attempt + 1), 16))
                    continue
                raise RuntimeError(f"OpenRouter API error: {error}")
            choices = body.get("choices")
            if not isinstance(choices, list) or not choices:
                if attempt < 4:
                    time.sleep(min(2 ** (attempt + 1), 16))
                    continue
                raise RuntimeError(f"OpenRouter response missing choices: {body}")
            choice = choices[0]
            message = choice.get("message") if isinstance(choice, dict) else None
            if not isinstance(message, dict):
                raise RuntimeError("OpenRouter response missing assistant message")
            # Keep provider usage next to the response only until run_agent
            # aggregates it.  The private field is removed before the message
            # is sent back to OpenRouter on the next tool round.
            usage = body.get("usage")
            if isinstance(usage, dict):
                message["_causalflow_usage"] = usage
            message["_causalflow_finish_reason"] = choice.get("finish_reason")
            return message
        except urllib.error.HTTPError as exc:
            if attempt < 4 and exc.code in {408, 409, 429, 500, 502, 503, 504}:
                time.sleep(min(2 ** (attempt + 1), 16))
                continue
            raise RuntimeError(describe_openrouter_http_error(exc)) from exc
        except (json.JSONDecodeError, *retryable_transport_errors) as exc:
            last_transport_error = exc
            if attempt == 4:
                break
            time.sleep(min(2 ** (attempt + 1), 16))
    raise RuntimeError(
        "OpenRouter request failed after 5 attempts: "
        f"{type(last_transport_error).__name__}: {last_transport_error}"
    ) from last_transport_error


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _raw_file_digest(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonical_json(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_JSON_KEYS
        }
    if isinstance(value, list):
        return [_canonical_json(item) for item in value]
    return value


def _json_digest(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    rendered = json.dumps(
        _canonical_json(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "json:" + _sha256_bytes(rendered)


def _normalise_ooxml_xml(name: str, data: bytes) -> bytes:
    if name != "docProps/core.xml":
        return data
    # Office writers update these fields even when every slide, cell, style,
    # formula, and relationship remains unchanged.
    return re.sub(
        rb"(<dcterms:(?:created|modified)\b[^>]*>).*?(</dcterms:(?:created|modified)>)",
        rb"\1<CANONICAL-TIME>\2",
        data,
        flags=re.DOTALL,
    )


def _ooxml_digest(path: str) -> str:
    digest = hashlib.sha256()
    with zipfile.ZipFile(path) as package:
        names = sorted(info.filename for info in package.infolist() if not info.is_dir())
        for name in names:
            data = _normalise_ooxml_xml(name, package.read(name))
            encoded_name = name.encode("utf-8")
            digest.update(struct.pack(">I", len(encoded_name)))
            digest.update(encoded_name)
            digest.update(struct.pack(">Q", len(data)))
            digest.update(data)
    return "ooxml:" + digest.hexdigest()


def _normalise_maven_properties(data: bytes) -> bytes:
    """Remove only Maven Archiver's generated wall-clock comment.

    Maven 3 writes ``#Generated by Maven`` followed by the current build time
    into ``pom.properties``.  Group/artifact/version and every other byte stay
    significant; non-Maven properties files are left untouched.
    """
    if not data.startswith(b"#Generated by Maven\n#"):
        return data
    lines = data.splitlines(keepends=True)
    if len(lines) < 5 or not all(
        any(line.startswith(prefix) for line in lines[2:])
        for prefix in (b"groupId=", b"artifactId=", b"version=")
    ):
        return data
    return lines[0] + b"#<CANONICAL-MAVEN-TIME>\n" + b"".join(lines[2:])


def _jar_digest(path: str) -> str:
    """Hash JAR semantics while ignoring ZIP/build timestamps only.

    Repeated Maven builds of identical source can differ in entry timestamps
    and the generated timestamp comment in META-INF/.../pom.properties.  Entry
    names, contents and non-time ZIP metadata remain part of this digest.
    """
    digest = hashlib.sha256()
    with zipfile.ZipFile(path) as package:
        infos = sorted((info for info in package.infolist() if not info.is_dir()), key=lambda info: info.filename)
        for info in infos:
            name = info.filename
            data = package.read(info)
            if name.endswith("/pom.properties"):
                data = _normalise_maven_properties(data)
            encoded_name = name.encode("utf-8")
            digest.update(struct.pack(">I", len(encoded_name)))
            digest.update(encoded_name)
            digest.update(struct.pack(">Q", len(data)))
            digest.update(data)
            digest.update(struct.pack(">I", info.compress_type))
            digest.update(info.comment)
            digest.update(info.extra)
            digest.update(struct.pack(">IIIII", info.internal_attr, info.external_attr, info.create_system, info.flag_bits, info.create_version))
    return "jar-semantic:" + digest.hexdigest()


def _maven_properties_digest(path: str) -> str:
    with open(path, "rb") as handle:
        data = handle.read()
    normalised = _normalise_maven_properties(data)
    if normalised == data:
        raise ValueError("not a generated Maven pom.properties file")
    return "maven-properties:" + _sha256_bytes(normalised)


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _png_digest(path: str) -> str:
    with open(path, "rb") as handle:
        data = handle.read()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("invalid PNG signature")
    offset = 8
    ihdr = b""
    palette = b""
    transparency = b""
    compressed = bytearray()
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            ihdr = chunk
        elif chunk_type == b"PLTE":
            palette = chunk
        elif chunk_type == b"tRNS":
            transparency = chunk
        elif chunk_type == b"IDAT":
            compressed.extend(chunk)
        elif chunk_type == b"IEND":
            break
    if len(ihdr) != 13:
        raise ValueError("PNG is missing IHDR")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", ihdr
    )
    if compression != 0 or filtering != 0 or interlace != 0:
        raise ValueError("unsupported PNG encoding")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError("unsupported PNG colour type")
    row_bytes = (width * channels * bit_depth + 7) // 8
    bytes_per_pixel = max(1, (channels * bit_depth + 7) // 8)
    filtered_rows = zlib.decompress(bytes(compressed))
    expected = height * (row_bytes + 1)
    if len(filtered_rows) != expected:
        raise ValueError("unexpected PNG scanline length")
    rows: list[bytes] = []
    previous = bytearray(row_bytes)
    cursor = 0
    for _ in range(height):
        filter_type = filtered_rows[cursor]
        source = filtered_rows[cursor + 1 : cursor + 1 + row_bytes]
        cursor += row_bytes + 1
        decoded = bytearray(row_bytes)
        for index, value in enumerate(source):
            left = decoded[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            above = previous[index]
            upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                predictor = _paeth(left, above, upper_left)
            else:
                raise ValueError("unsupported PNG filter")
            decoded[index] = (value + predictor) & 0xFF
        rows.append(bytes(decoded))
        previous = decoded
    semantic = ihdr + palette + transparency + b"".join(rows)
    return "png:" + _sha256_bytes(semantic)


def _pdf_digest(path: str) -> str:
    """Keep all PDF bytes except the volatile update ID in a plain trailer.

    MuPDF changes the second /ID on every save, even for identical documents.
    Preserve the original ID, metadata, streams, objects and cross references.
    Unsupported/encrypted trailers retain the exact byte digest.
    """
    with open(path, 'rb') as handle:
        data = handle.read()
    start = data.rfind(b'\ntrailer')
    if not data.startswith(b'%PDF-') or start < 0:
        raise ValueError('PDF has no supported plain trailer')
    tail = data[start:]
    if not re.fullmatch(rb'\ntrailer\s*<<.*?>>\s*startxref\s*\d+\s*%%EOF\s*', tail, re.DOTALL):
        raise ValueError('unsupported PDF trailer')
    if b'/Encrypt' in tail:
        raise ValueError('encrypted PDF requires exact digest')
    pattern = rb'(/ID\s*\[\s*<[0-9A-Fa-f]{32}>\s*<)[0-9A-Fa-f]{32}(>\s*\])'
    if len(re.findall(pattern, tail)) != 1:
        raise ValueError('unsupported PDF identifier')
    tail = re.sub(pattern, lambda match: match[1] + b'0' * 32 + match[2], tail)
    return 'pdf-update-id:' + _sha256_bytes(data[:start] + tail)


def content_digest(path: str) -> str:
    suffix = os.path.splitext(path)[1].lower()
    try:
        if suffix == ".json":
            return _json_digest(path)
        if suffix in {".pptx", ".xlsx"}:
            return _ooxml_digest(path)
        if suffix == ".png":
            return _png_digest(path)
        if suffix == ".pdf":
            return _pdf_digest(path)
        if suffix == ".jar":
            return _jar_digest(path)
        if os.path.basename(path) == "pom.properties":
            return _maven_properties_digest(path)
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile, zlib.error):
        # Invalid or unsupported files still receive an exact byte digest.
        pass
    return _raw_file_digest(path)


def snapshot_path_ignored(relative: str) -> bool:
    lowered = relative.lower()
    components = lowered.split("/")
    name = lowered.rsplit("/", 1)[-1]
    return (
        any(component in SNAPSHOT_IGNORE_NAMES for component in components)
        or name.endswith(".log")
        or name.endswith("_log.txt")
        or name.endswith("-log.txt")
    )


def workspace_manifest(cwd: str) -> dict[str, str]:
    manifest: dict[str, str] = {}
    base = os.path.realpath(cwd)
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(name for name in dirs if name not in SNAPSHOT_IGNORE_NAMES)
        for name in sorted(files):
            if name in SNAPSHOT_IGNORE_NAMES:
                continue
            path = os.path.join(root, name)
            try:
                stat = os.stat(path, follow_symlinks=False)
                if not os.path.isfile(path) or os.path.islink(path):
                    continue
                relative = os.path.relpath(path, base).replace(os.sep, "/")
                if snapshot_path_ignored(relative):
                    continue
                manifest[relative] = content_digest(path)
            except OSError:
                continue
    return manifest


def resource_delta(
    before: dict[str, str],
    after: dict[str, str],
    observed_reads: list[str],
) -> dict[str, Any]:
    observed_writes = sorted(
        path for path, digest in after.items() if before.get(path) != digest
    )
    return {
        "observed_reads": sorted(path for path in observed_reads if path in before),
        "observed_writes": observed_writes,
        # Persist the exact post-command content identity.  A matching reward
        # and pytest count are too weak to establish replay fidelity: two
        # different artifacts can fail the same checks.  These hashes let the
        # host replay compare the verifier-visible workspace byte-for-byte.
        "observed_write_hashes": {
            path: after[path] for path in observed_writes
        },
        "observed_deletes": sorted(path for path in before if path not in after),
    }


def _run_command(
    command: str,
    cwd: str,
    *,
    env: dict[str, str],
    timeout: float,
) -> tuple[subprocess.CompletedProcess[str] | None, str, str, bool]:
    process = subprocess.Popen(
        ["/bin/bash", "-lc", command],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        trailing_stdout, trailing_stderr = process.communicate()
        # ``communicate`` returns the complete buffered stream after the
        # process group is killed.  Re-appending the partial stream carried by
        # TimeoutExpired duplicates output and can mix bytes with text.
        stdout = trailing_stdout or ""
        stderr = trailing_stderr or ""
        return None, stdout, stderr, True
    return (
        subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr),
        stdout,
        stderr,
        False,
    )


def run_shell(command: str, cwd: str) -> tuple[str, bool]:
    before = workspace_manifest(cwd)
    os.makedirs(PYTHON_AUDIT_DIR, exist_ok=True)
    sitecustomize = os.path.join(PYTHON_AUDIT_DIR, "sitecustomize.py")
    with open(sitecustomize, "w") as handle:
        handle.write(PYTHON_AUDIT_SOURCE)
    audit_log = os.path.join(PYTHON_AUDIT_DIR, f"audit-{uuid.uuid4().hex}.jsonl")
    command_env = os.environ.copy()
    existing_pythonpath = command_env.get("PYTHONPATH", "")
    command_env["PYTHONPATH"] = (
        PYTHON_AUDIT_DIR
        if not existing_pythonpath
        else f"{PYTHON_AUDIT_DIR}{os.pathsep}{existing_pythonpath}"
    )
    command_env["CAUSALFLOW_AUDIT_ROOT"] = os.path.realpath(cwd)
    command_env["CAUSALFLOW_AUDIT_LOG"] = audit_log
    result, stdout, stderr, timed_out = _run_command(
        command, cwd, env=command_env, timeout=120
    )
    if timed_out:
        output = f"command timed out after 120s\n{stdout}\n{stderr}"
        succeeded = False
    else:
        assert result is not None
        output = (
            f"return_code={result.returncode}\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )
        succeeded = result.returncode == 0
    after = workspace_manifest(cwd)
    observed_reads: list[str] = []
    try:
        with open(audit_log) as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("operation") == "read" and isinstance(
                    record.get("path"), str
                ):
                    observed_reads.append(record["path"])
    except (OSError, json.JSONDecodeError):
        pass
    try:
        os.unlink(audit_log)
    except OSError:
        pass
    marker = RESOURCE_EVENT_PREFIX + json.dumps(
        resource_delta(before, after, list(dict.fromkeys(observed_reads))),
        separators=(",", ":"),
    )
    combined = f"{output}\n{marker}"
    return combined[-MAX_TOOL_OUTPUT:], succeeded


def parse_command(call: dict[str, Any]) -> str:
    function = call.get("function")
    if not isinstance(function, dict) or function.get("name") != "run_shell":
        return ""
    arguments = function.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return ""
    if not isinstance(arguments, dict):
        return ""
    command = arguments.get("command")
    return command.strip() if isinstance(command, str) else ""


def load_skill_context(root: str = "/skills") -> tuple[str, list[str]]:
    """Read the deployed skill bundle once so with-skill runs are auditable.

    Full-featured coding agents discover their own skill directories.  This
    dependency-light ACP agent has no native skill loader, so relying on the
    model to remember an exploratory ``ls /skills`` call makes a with-skill
    condition stochastic.  Loading the bundle here matches prompt-injected
    skill agents and emits an explicit read event into the trajectory.
    """

    if not os.path.isdir(root):
        return "", []
    paths: list[str] = []
    chunks: list[str] = []
    used = 0
    for directory, _subdirs, files in os.walk(root):
        if "SKILL.md" not in files:
            continue
        path = os.path.join(directory, "SKILL.md")
        try:
            content = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        header = f"\n===== {path} =====\n"
        remaining = MAX_SKILL_CONTEXT - used - len(header)
        if remaining <= 0:
            break
        rendered = header + content[:remaining]
        chunks.append(rendered)
        used += len(rendered)
        paths.append(os.path.realpath(path))
        if used >= MAX_SKILL_CONTEXT:
            break
    return "".join(chunks), paths


def run_agent(
    *,
    model: str,
    instruction: str,
    cwd: str,
    session_id: str,
) -> dict[str, int]:
    skill_context, skill_paths = load_skill_context()
    if skill_paths:
        preload_id = f"skill-preload-{uuid.uuid4().hex[:10]}"
        # This is a real harness-level skill activation: the full deployed
        # SKILL.md text is inserted into the model context below.  Emit the
        # canonical ACP kind so BenchFlow's skill-usage metric does not report
        # a false zero merely because this lightweight agent has no separate
        # invoke_skill tool.
        preload_title = "activate_skill"
        emit_tool_call(
            session_id,
            preload_id,
            preload_title,
            kind="skill",
        )
        marker = RESOURCE_EVENT_PREFIX + json.dumps(
            {
                "observed_reads": skill_paths,
                "observed_writes": [],
                "observed_deletes": [],
            },
            separators=(",", ":"),
        )
        emit_tool_result(
            session_id,
            preload_id,
            "Tool: activate_skill\n"
            f"[skill: {', '.join(skill_paths)}]\n"
            f"loaded_skills={len(skill_paths)}\n{marker}",
            succeeded=True,
        )
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are solving a terminal benchmark inside an isolated Docker container. "
                "Use run_shell to inspect the workspace and implement the requested artifact. "
                "Do the work; do not merely explain it. Check your output when practical. "
                "If /skills exists, list it first and read the relevant top-level SKILL.md "
                "files before implementing. Multiple complementary skills may all be "
                "required, but do not assume every bundled skill is relevant. Avoid dumping "
                "large input files: inspect their schema with head, wc, or a short script. "
                "For multi-line programs, create a source file with a shell heredoc instead "
                "of compressing Python control flow into python -c. "
                f"Your working directory is {cwd}."
                + (
                    "\n\nThe following deployed SkillsBench skills are available. "
                    "Apply their relevant procedures while solving the task:"
                    + skill_context
                    if skill_context
                    else ""
                )
            ),
        },
        {"role": "user", "content": instruction},
    ]
    usage_totals = {
        "inputTokens": 0,
        "outputTokens": 0,
        "totalTokens": 0,
        "cachedReadTokens": 0,
        "thoughtTokens": 0,
    }
    for _round in range(MAX_TOOL_ROUNDS):
        assistant = openrouter_chat(model, messages)
        raw_usage = assistant.pop("_causalflow_usage", None)
        finish_reason = assistant.pop("_causalflow_finish_reason", None)
        if isinstance(raw_usage, dict):
            usage_totals["inputTokens"] += int(raw_usage.get("prompt_tokens") or 0)
            usage_totals["outputTokens"] += int(
                raw_usage.get("completion_tokens") or 0
            )
            usage_totals["totalTokens"] += int(raw_usage.get("total_tokens") or 0)
            prompt_details = raw_usage.get("prompt_tokens_details")
            if isinstance(prompt_details, dict):
                usage_totals["cachedReadTokens"] += int(
                    prompt_details.get("cached_tokens") or 0
                )
            completion_details = raw_usage.get("completion_tokens_details")
            if isinstance(completion_details, dict):
                usage_totals["thoughtTokens"] += int(
                    completion_details.get("reasoning_tokens") or 0
                )
        if finish_reason in {"length", "error"}:
            raise RuntimeError(
                f"OpenRouter response ended with finish_reason={finish_reason}"
            )
        tool_calls = assistant.get("tool_calls")
        messages.append(assistant)
        if not isinstance(tool_calls, list) or not tool_calls:
            content = assistant.get("content")
            emit_text(session_id, str(content or "Task completed."))
            return usage_totals

        for raw_call in tool_calls:
            if not isinstance(raw_call, dict):
                continue
            call_id = str(raw_call.get("id") or f"call-{uuid.uuid4().hex[:10]}")
            command = parse_command(raw_call)
            if not command:
                result_text = (
                    "Invalid run_shell arguments: expected a non-empty command"
                )
                emit_tool_call(session_id, call_id, "[invalid run_shell call]")
                emit_tool_result(session_id, call_id, result_text, succeeded=False)
            else:
                emit_tool_call(session_id, call_id, command)
                result_text, succeeded = run_shell(command, cwd)
                command_marker = "CAUSALFLOW_COMMAND_ZLIB_B64=" + base64.b64encode(
                    zlib.compress(command.encode("utf-8"), level=9)
                ).decode("ascii")
                emit_tool_result(
                    session_id,
                    call_id,
                    f"{result_text}\n{command_marker}",
                    succeeded=succeeded,
                )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result_text,
                }
            )
    emit_text(session_id, f"Stopped after {MAX_TOOL_ROUNDS} tool rounds.")
    return usage_totals


def prompt_text(params: object) -> str:
    if not isinstance(params, dict):
        return ""
    chunks: list[str] = []
    for part in params.get("prompt") or []:
        if isinstance(part, dict) and part.get("type") == "text":
            chunks.append(str(part.get("text") or ""))
    return "\n".join(chunks)


def main() -> int:
    model = os.environ.get(
        "CAUSALFLOW_OPENROUTER_MODEL", "anthropic/claude-opus-4.7"
    )
    cwd = os.getcwd()
    session_id = f"causalflow-{uuid.uuid4().hex[:10]}"
    while True:
        try:
            message = recv()
        except EOFError:
            break
        method = str(message.get("method") or "")
        request_id = message.get("id")
        params = message.get("params")
        if method == "initialize":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": 1,
                        "agentCapabilities": {
                            "loadSession": False,
                            "promptCapabilities": {"image": False, "audio": False},
                        },
                        "agentInfo": {
                            "name": "causalflow-openrouter-acp",
                            "version": "0.1",
                        },
                    },
                }
            )
        elif method == "session/new":
            if isinstance(params, dict) and params.get("cwd"):
                cwd = str(params["cwd"])
            session_id = f"causalflow-{uuid.uuid4().hex[:10]}"
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"sessionId": session_id},
                }
            )
        elif method == "session/set_model":
            if isinstance(params, dict) and params.get("modelId"):
                model = str(params["modelId"])
            send({"jsonrpc": "2.0", "id": request_id, "result": {}})
        elif method == "session/prompt":
            usage = None
            try:
                usage = run_agent(
                    model=model,
                    instruction=prompt_text(params),
                    cwd=cwd,
                    session_id=session_id,
                )
            except Exception as exc:
                emit_text(session_id, f"Agent error: {type(exc).__name__}: {exc}")
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"stopReason": "end_turn", "usage": usage},
                }
            )
        elif method in {"session/cancel", "session/set_config_option"}:
            send({"jsonrpc": "2.0", "id": request_id, "result": {}})
        elif request_id is not None:
            send({"jsonrpc": "2.0", "id": request_id, "result": {}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
