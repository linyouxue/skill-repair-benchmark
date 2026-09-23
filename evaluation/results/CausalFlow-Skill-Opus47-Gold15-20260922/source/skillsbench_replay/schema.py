"""Data carried between the SkillsBench trace, graph, and replay layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FileState:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class FileDelta:
    path: str
    change: str
    before_sha256: Optional[str]
    after_sha256: Optional[str]


@dataclass
class CommandEvent:
    """One terminal-like tool call extracted from a SkillsBench trajectory.

    ``argument_source`` is deliberately explicit. BenchFlow 0.6.3 exports ACP
    tool arguments as ``{}``; in that case ``extra.title`` is only fallback
    evidence and must not be presented as an observed structured argument.
    """

    step_id: int
    atif_step_id: int
    tool_call_id: str
    kind: str
    title: str
    command: Optional[str]
    argument_source: str
    status: str
    output: str = ""
    inferred_reads: Tuple[str, ...] = ()
    inferred_writes: Tuple[str, ...] = ()
    inferred_deletes: Tuple[str, ...] = ()
    observed_reads: Tuple[str, ...] = ()
    observed_writes: Tuple[str, ...] = ()
    observed_write_hashes: Dict[str, str] = field(default_factory=dict)
    replayable: bool = False
    warnings: Tuple[str, ...] = ()
    terminal_arguments: Dict[str, Any] = field(default_factory=dict)
    wait_for_step_id: Optional[int] = None
    replay_timeout: Optional[float] = None
    completion_output: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedRun:
    session_id: str
    agent_name: str
    model_name: Optional[str]
    events: List[CommandEvent]
    reward: Optional[float] = None
    verifier_passed: Optional[bool] = None
    warnings: List[str] = field(default_factory=list)
    source_paths: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "model_name": self.model_name,
            "events": [event.to_dict() for event in self.events],
            "reward": self.reward,
            "verifier_passed": self.verifier_passed,
            "warnings": self.warnings,
            "source_paths": self.source_paths,
        }


@dataclass
class ReplayRun:
    mode: str
    executed_step_ids: List[int]
    manifest: Dict[str, str]
    verifier_passed: Optional[bool]
    workspace: str
    failure_reason: Optional[str] = None

    def observable_signature(
        self,
    ) -> Tuple[Tuple[Tuple[str, str], ...], Optional[bool]]:
        return tuple(sorted(self.manifest.items())), self.verifier_passed

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReplayExperiment:
    full: ReplayRun
    selective: ReplayRun
    agreement: bool
    command_reduction: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "full": self.full.to_dict(),
            "selective": self.selective.to_dict(),
            "agreement": self.agreement,
            "command_reduction": self.command_reduction,
        }
