"""Profile-isolated local file persistence with generated filenames."""

from pathlib import Path

from app.ingestion.types import StoredFile, ValidatedUpload


class LocalDocumentStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _resolve_inside_root(self, relative_path: Path) -> Path:
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Generated document path escaped the upload directory.")
        return target

    def store(self, profile_id: str, document_id: str, upload: ValidatedUpload) -> StoredFile:
        stored_filename = f"{document_id}{upload.extension}"
        relative_path = Path(profile_id) / stored_filename
        target = self._resolve_inside_root(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stored:
            stored.write(upload.content)
        return StoredFile(
            stored_filename=stored_filename,
            relative_path=relative_path.as_posix(),
            absolute_path=target,
        )

    def resolve(self, relative_path: str) -> Path:
        return self._resolve_inside_root(Path(relative_path))

    def remove(self, stored_file: StoredFile) -> None:
        stored_file.absolute_path.unlink(missing_ok=True)
