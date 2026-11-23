from pathlib import Path
from uuid import UUID


class LocalRecordingStorage:
    """Stores recordings under a configured local directory using generated names."""

    def __init__(self, root: str | Path = "storage/recordings"):
        self.root = Path(root)

    def save(self, recording_id: UUID, suffix: str, content: bytes) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        name = f"{recording_id}{suffix}"
        (self.root / name).write_bytes(content)
        return name

    def delete(self, storage_name: str) -> None:
        (self.root / storage_name).unlink(missing_ok=True)
