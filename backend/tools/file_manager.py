"""
celia.pro File Manager Tool
=============================
Read, write, and manage files with path traversal protection.
"""

from tools.base import BaseTool
from core.tool_security import RiskLevel
from typing import Dict, Any
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# Workspace root - files outside this are inaccessible
WORKSPACE_ROOT = "/home/user"


class FileManagerTool(BaseTool):
    """File management with security controls."""

    name = "file_manager"
    description = "Manage files in the workspace: read, write, list, create directories, delete, and get file information. All operations are restricted to the workspace directory."
    category = "file_management"
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "append", "list", "mkdir", "delete", "info", "search"],
                "description": "The file operation to perform"
            },
            "path": {
                "type": "string",
                "description": "File or directory path (relative to workspace)"
            },
            "content": {
                "type": "string",
                "description": "Content to write (for write/append actions)"
            },
            "pattern": {
                "type": "string",
                "description": "Search pattern (for search action, supports glob patterns)"
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to search recursively",
                "default": False
            }
        },
        "required": ["action"]
    }

    def __init__(self, workspace_root: str = WORKSPACE_ROOT):
        self.workspace_root = os.path.realpath(workspace_root)

    def _resolve_path(self, path: str) -> str:
        """Resolve a path relative to the workspace root with traversal protection."""
        if not path:
            return self.workspace_root

        # Resolve to absolute
        if os.path.isabs(path):
            resolved = os.path.realpath(path)
        else:
            resolved = os.path.realpath(os.path.join(self.workspace_root, path))

        # CRITICAL: Must be within workspace
        if not resolved.startswith(self.workspace_root + os.sep) and resolved != self.workspace_root:
            from core.exceptions import ValidationError
            raise ValidationError(
                message=f"Path traversal blocked: path must be within workspace",
                field="path"
            )

        return resolved

    async def execute(self, action: str, path: str = "", content: str = "",
                     pattern: str = "", recursive: bool = False, **kwargs) -> str:
        """Execute file operation with security checks."""
        try:
            resolved_path = self._resolve_path(path)
        except ValueError as e:
            return f"Security Error: {str(e)}"

        actions = {
            "read": lambda: self._read_file(resolved_path),
            "write": lambda: self._write_file(resolved_path, content),
            "append": lambda: self._append_file(resolved_path, content),
            "list": lambda: self._list_directory(resolved_path, recursive),
            "mkdir": lambda: self._make_directory(resolved_path),
            "delete": lambda: self._delete_path(resolved_path),
            "info": lambda: self._get_info(resolved_path),
            "search": lambda: self._search_files(resolved_path, pattern),
        }

        handler = actions.get(action)
        if not handler:
            return f"Unknown action: {action}. Available: {', '.join(actions.keys())}"

        try:
            return handler()
        except PermissionError:
            return f"Permission denied for path: {path}"
        except Exception as e:
            return f"Error: {str(e)}"

    def _read_file(self, path: str) -> str:
        """Read a file's contents."""
        if not os.path.exists(path):
            return f"Error: File not found: {path}"
        if os.path.isdir(path):
            return self._list_directory(path, False)

        # Check file size before reading
        file_size = os.path.getsize(path)
        if file_size > 1_000_000:  # 1MB limit
            return f"Error: File too large ({self._format_size(file_size)}). Maximum: 1MB"

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if len(content) > 10000:
                return f"File content (first 10000 chars of {len(content)}):\n{content[:10000]}..."
            return content
        except UnicodeDecodeError:
            return f"Error: File is not a text file (binary content detected)"

    def _write_file(self, path: str, content: str) -> str:
        """Write content to a file."""
        if not content and not isinstance(content, str):
            return "Error: Content is required for write action"

        # Prevent writing to system files
        protected = ["/etc", "/usr", "/var", "/root", "/home/user/.bashrc",
                     "/home/user/.profile", "/home/user/.ssh"]
        for p in protected:
            if path.startswith(p):
                return f"Error: Cannot write to protected path: {p}"

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {path}"

    def _append_file(self, path: str, content: str) -> str:
        """Append content to a file."""
        if not content and not isinstance(content, str):
            return "Error: Content is required for append action"

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully appended {len(content)} characters to {path}"

    def _list_directory(self, path: str, recursive: bool = False) -> str:
        """List directory contents."""
        if not os.path.exists(path):
            path = self.workspace_root
        if not os.path.isdir(path):
            return f"Error: Not a directory: {path}"

        entries = []
        max_entries = 200

        if recursive:
            for root, dirs, files in os.walk(path):
                # Skip hidden directories and node_modules
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
                rel_root = os.path.relpath(root, self.workspace_root)
                for d in dirs[:10]:  # Limit per directory
                    entries.append(f"📁 {os.path.join(rel_root, d)}/")
                for f in files[:50]:  # Limit per directory
                    if not f.startswith('.'):
                        entries.append(f"📄 {os.path.join(rel_root, f)}")
                if len(entries) >= max_entries:
                    entries.append(f"... (truncated at {max_entries} entries)")
                    break
        else:
            try:
                sorted_entries = sorted(os.listdir(path))
            except PermissionError:
                return f"Error: Permission denied for directory"

            for entry in sorted_entries:
                if entry.startswith('.'):
                    continue
                full = os.path.join(path, entry)
                if os.path.isdir(full):
                    entries.append(f"📁 {entry}/")
                else:
                    try:
                        size = os.path.getsize(full)
                        entries.append(f"📄 {entry} ({self._format_size(size)})")
                    except OSError:
                        entries.append(f"📄 {entry}")
                if len(entries) >= max_entries:
                    entries.append(f"... (truncated at {max_entries} entries)")
                    break

        if not entries:
            return "Directory is empty"
        return "\n".join(entries)

    def _make_directory(self, path: str) -> str:
        """Create a directory."""
        os.makedirs(path, exist_ok=True)
        return f"Created directory: {path}"

    def _delete_path(self, path: str) -> str:
        """Delete a file or directory with safety checks."""
        # Extra safety: prevent deleting workspace root or system paths
        if os.path.realpath(path) == self.workspace_root:
            return "Error: Cannot delete workspace root"

        protected = ["/home/user/novamind", "/home/user/.git"]
        for p in protected:
            if os.path.realpath(path).startswith(p):
                return f"Error: Cannot delete protected path: {p}"

        if os.path.isfile(path):
            os.remove(path)
            return f"Deleted file: {path}"
        elif os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
            return f"Deleted directory: {path}"
        return f"Path not found: {path}"

    def _get_info(self, path: str) -> str:
        """Get file/directory information."""
        if not os.path.exists(path):
            return f"Path not found: {path}"
        stat = os.stat(path)
        info = {
            "path": path,
            "type": "directory" if os.path.isdir(path) else "file",
            "size": self._format_size(stat.st_size),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }
        return json.dumps(info, indent=2)

    def _search_files(self, path: str, pattern: str) -> str:
        """Search for files matching a pattern."""
        import fnmatch
        if not pattern:
            return "Error: Search pattern is required"

        matches = []
        max_matches = 50

        for root, dirs, files in os.walk(path):
            # Skip hidden directories and node_modules
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']

            for f in files:
                if fnmatch.fnmatch(f, pattern):
                    rel_path = os.path.relpath(os.path.join(root, f), self.workspace_root)
                    matches.append(rel_path)
                    if len(matches) >= max_matches:
                        break
            if len(matches) >= max_matches:
                break

        if not matches:
            return f"No files matching '{pattern}' found"
        return f"Found {len(matches)} matching files:\n" + "\n".join(matches)

    @staticmethod
    def _format_size(size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
