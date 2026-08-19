"""Manage versioned and stable paths for generated audio assets."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from weatherbox.errors import AssetPublicationError
from weatherbox.models import AnnouncementKind, AudioAsset


class AssetManager:
    """Publish generated audio to versioned and stable public paths."""

    def __init__(self, generated_dir: Path, public_dir: Path) -> None:
        """Initialize the manager with generated and public root directories."""
        self.generated_dir = generated_dir
        self.public_dir = public_dir

    def paths(self, location_id: str, kind: AnnouncementKind, playback_at) -> AudioAsset:
        """Build the versioned and public paths for an announcement."""
        date_dir = self.generated_dir / location_id / playback_at.date().isoformat()
        filename = f"{playback_at:%H-%M}-{kind.short_name}.mp3"
        return AudioAsset(
            location_id=location_id,
            kind=kind,
            playback_at=playback_at,
            versioned_path=date_dir / filename,
            public_path=self.public_dir / location_id / kind.filename,
        )

    def publish(self, source: Path, asset: AudioAsset) -> AudioAsset:
        """Atomically copy a generated MP3 to its versioned and public paths."""
        if not source.is_file() or source.stat().st_size == 0:
            raise AssetPublicationError("The asset to be published is missing or empty")
        asset.versioned_path.parent.mkdir(parents=True, exist_ok=True)
        asset.public_path.parent.mkdir(parents=True, exist_ok=True)
        version_temp = self._copy_to_temporary(source, asset.versioned_path.parent)
        public_temp: Path | None = None
        try:
            os.replace(version_temp, asset.versioned_path)
            public_temp = self._copy_to_temporary(asset.versioned_path, asset.public_path.parent)
            os.replace(public_temp, asset.public_path)
        except OSError as exc:
            raise AssetPublicationError(f"The asset could not be published atomically: {exc}") from exc
        finally:
            version_temp.unlink(missing_ok=True)
            if public_temp:
                public_temp.unlink(missing_ok=True)
        return asset

    @staticmethod
    def _copy_to_temporary(source: Path, target_dir: Path) -> Path:
        """Copy a source file to a flushed temporary file in ``target_dir``."""
        fd, name = tempfile.mkstemp(prefix=".weatherbox-", suffix=".mp3", dir=target_dir)
        os.close(fd)
        temporary = Path(name)
        try:
            shutil.copyfile(source, temporary)
            # Windows only permits FlushFileBuffers through a writable handle.
            with temporary.open("r+b") as handle:
                os.fsync(handle.fileno())
            return temporary
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
