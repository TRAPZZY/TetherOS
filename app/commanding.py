"""Typed command contracts and lifecycle events for TRAP HUB."""

from collections.abc import MutableMapping
from dataclasses import dataclass, field, replace
import threading
import time
from typing import Any, Callable, Dict, Iterator, Mapping, Optional, Sequence


CommandHandler = Callable[[Sequence[str]], Any]


@dataclass(frozen=True)
class CommandDescriptor:
    name: str
    handler: CommandHandler = field(repr=False, compare=False)
    summary: str = ""
    category: str = "general"
    usage: str = ""
    risk: str = "normal"
    accepts_stdin: bool = True
    produces_structured_data: bool = False


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    argv: tuple
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    data: Any = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def duration_ms(self) -> int:
        return max(0, round((self.finished_at - self.started_at) * 1000))


@dataclass(frozen=True)
class CommandEvent:
    kind: str
    command_id: str
    timestamp: float
    argv: tuple
    payload: Mapping[str, Any] = field(default_factory=dict)


class EventBus:
    """Small synchronous event bus with subscriber failure isolation."""

    def __init__(self):
        self._subscribers = []
        self._lock = threading.RLock()

    def subscribe(self, callback):
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

        def unsubscribe():
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def publish(self, event: CommandEvent):
        with self._lock:
            subscribers = tuple(self._subscribers)
        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                # Telemetry and UI observers must never break command execution.
                continue


class CommandRegistry(MutableMapping):
    """Mapping-compatible command registry backed by typed descriptors."""

    def __init__(self, commands: Optional[Mapping[str, CommandHandler]] = None):
        self._descriptors: Dict[str, CommandDescriptor] = {}
        if commands:
            self.update(commands)

    def __getitem__(self, name: str) -> CommandHandler:
        return self._descriptors[name].handler

    def __setitem__(self, name: str, handler: CommandHandler):
        normalized = name.lower()
        existing = self._descriptors.get(normalized)
        if existing:
            self._descriptors[normalized] = replace(existing, handler=handler)
        else:
            self._descriptors[normalized] = CommandDescriptor(normalized, handler)

    def __delitem__(self, name: str):
        del self._descriptors[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._descriptors)

    def __len__(self) -> int:
        return len(self._descriptors)

    def describe(self, name: str, **metadata) -> CommandDescriptor:
        normalized = name.lower()
        descriptor = self._descriptors[normalized]
        allowed = {
            "summary", "category", "usage", "risk", "accepts_stdin",
            "produces_structured_data",
        }
        unknown = set(metadata) - allowed
        if unknown:
            raise TypeError(f"Unknown command metadata: {', '.join(sorted(unknown))}")
        descriptor = replace(descriptor, **metadata)
        self._descriptors[normalized] = descriptor
        return descriptor

    def descriptor(self, name: str) -> Optional[CommandDescriptor]:
        return self._descriptors.get(name.lower())

    def descriptors(self):
        return tuple(self._descriptors.values())

    def complete(self, prefix: str):
        normalized = prefix.lower()
        return tuple(name for name in self if name.startswith(normalized))


def command_event(kind, command_id, argv, **payload):
    return CommandEvent(
        kind=kind,
        command_id=command_id,
        timestamp=time.time(),
        argv=tuple(argv),
        payload=payload,
    )
