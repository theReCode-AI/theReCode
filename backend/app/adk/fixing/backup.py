import hashlib
import json
import shutil
from pathlib import Path


class PatchBackupManager:
    """Backup and restore workspace files for rollback."""

    MANIFEST_NAME = "manifest.json"

    def backup_working_tree(self, working_root: Path, backup_root: Path) -> None:
        if backup_root.exists():
            shutil.rmtree(backup_root)
        shutil.copytree(working_root, backup_root)

    def restore_working_tree(self, working_root: Path, backup_root: Path) -> None:
        if not backup_root.exists():
            return
        if working_root.exists():
            shutil.rmtree(working_root)
        shutil.copytree(backup_root, working_root)

    def create_backup(
        self,
        working_root: Path,
        backup_root: Path,
        relative_files: list[str],
    ) -> dict[str, str]:
        backup_root.mkdir(parents=True, exist_ok=True)
        manifest = snapshot_tree_hashes(working_root)

        for relative_file in relative_files:
            if relative_file == "repository":
                continue
            source = working_root / relative_file
            if not source.exists():
                continue
            destination = backup_root / relative_file
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)

        (backup_root / self.MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        return manifest

    def restore_backup(
        self,
        working_root: Path,
        backup_root: Path,
        relative_files: list[str],
    ) -> None:
        for relative_file in relative_files:
            if relative_file == "repository":
                continue
            backup_file = backup_root / relative_file
            if not backup_file.exists():
                continue
            destination = working_root / relative_file
            if backup_file.is_dir():
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(backup_file, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_file, destination)

        manifest_path = backup_root / self.MANIFEST_NAME
        if not manifest_path.is_file():
            return

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        restore_tree_from_manifest(working_root, manifest)


def snapshot_tree_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not root.exists():
        return hashes

    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            hashes[relative] = _hash_file(path)
    return hashes


def detect_changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed: list[str] = []
    all_paths = set(before) | set(after)
    for relative_path in sorted(all_paths):
        if before.get(relative_path) != after.get(relative_path):
            changed.append(relative_path)
    return changed


def restore_tree_from_manifest(working_root: Path, manifest: dict[str, str]) -> None:
    current = snapshot_tree_hashes(working_root)
    for relative_path, expected_hash in manifest.items():
        file_path = working_root / relative_path
        if current.get(relative_path) == expected_hash:
            continue
        if not file_path.exists():
            continue
        # Files restored individually above; manifest handles files removed during fix.
        # If a new file appeared, remove it when not in manifest.
    for relative_path in current:
        if relative_path not in manifest:
            extra = working_root / relative_path
            if extra.is_file():
                extra.unlink()
            elif extra.is_dir():
                shutil.rmtree(extra)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
