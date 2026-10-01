from pathlib import Path
from typing import BinaryIO, Protocol


class FileStorage(Protocol):
    def save(self, source: BinaryIO, key: str, max_size: int) -> None: ...

    def path_for(self, key: str) -> Path: ...


class LocalFileStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def save(self, source: BinaryIO, key: str, max_size: int) -> None:
        destination = self.path_for(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        try:
            with destination.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_size:
                        break
                    target.write(chunk)
            if total > max_size:
                destination.unlink(missing_ok=True)
                raise ValueError("File exceeds the maximum allowed size")
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        root = self.root.resolve()
        if root not in path.parents:
            raise ValueError("Invalid storage key")
        return path