"""
celia.pro Shell Tool
=====================
Execute shell commands with strict security controls.
"""

from tools.base import BaseTool
from core.tool_security import RiskLevel
from typing import Dict, Any
import asyncio
import re
import shlex
import logging

logger = logging.getLogger(__name__)


# Allowed commands (whitelist approach)
ALLOWED_COMMANDS = {
    "ls", "cat", "head", "tail", "wc", "grep", "find", "echo",
    "pwd", "whoami", "date", "uname", "df", "du", "free", "uptime",
    "python3", "python", "node", "npm", "pip", "pip3",
    "git", "curl", "wget", "mkdir", "touch", "cp", "mv",
    "env", "which", "type", "file", "stat", "basename", "dirname",
    "sort", "uniq", "cut", "tr", "sed", "awk", "tee",
}

# Dangerous patterns that must never be allowed
BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"mkfs",
    r"dd\s+if=",
    r":\(\)",              # Fork bomb
    r"chmod\s+-R\s+777",
    r"sudo",
    r">\s*/dev/sd",
    r"curl.*\|\s*(sh|bash)",
    r"wget.*\|\s*(sh|bash)",
    r"\|\s*sh\b",
    r"\|\s*bash\b",
    r"eval\s+",
    r"exec\s+",
    r"\.\s+/",             # Source command
    r"kill\s+-9\s+(-|\d)", # Kill init/PID 1
    r"/etc/passwd",
    r"/etc/shadow",
    r"~/.ssh",
    r"\brm\b.*\b-\w*r\w*f\w*",  # rm -rf anything
]

# Maximum command length
MAX_COMMAND_LENGTH = 2000


class ShellTool(BaseTool):
    """Execute shell commands with security controls."""

    name = "shell"
    description = "Execute safe shell commands in the workspace. Use for system information, file operations, and development tasks. Dangerous commands are blocked."
    category = "execution"
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute"
            },
            "cwd": {
                "type": "string",
                "description": "Working directory (default: /home/user)",
                "default": "/home/user"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30, max: 60)",
                "default": 30
            }
        },
        "required": ["command"]
    }

    async def execute(self, command: str, cwd: str = "/home/user", timeout: int = 30, **kwargs) -> str:
        """Execute a shell command with security checks."""
        # Enforce limits
        timeout = min(max(timeout, 1), 60)

        if not command or not isinstance(command, str):
            return "Error: Command is required"

        command = command.strip()
        if len(command) > MAX_COMMAND_LENGTH:
            return f"Error: Command too long ({len(command)} > {MAX_COMMAND_LENGTH})"

        # Security check
        safety_error = self._check_safety(command)
        if safety_error:
            return f"Safety Check Failed: {safety_error}"

        # Validate working directory
        if not self._is_safe_cwd(cwd):
            cwd = "/home/user"

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                return f"Error: Command timed out after {timeout} seconds"

            result_parts = []
            if stdout:
                output = stdout.decode('utf-8', errors='replace')
                if output.strip():
                    # Limit output size
                    if len(output) > 10000:
                        output = output[:10000] + "\n[... truncated]"
                    result_parts.append(f"Output:\n{output.strip()}")
            if stderr:
                errors = stderr.decode('utf-8', errors='replace')
                if errors.strip():
                    result_parts.append(f"Stderr:\n{errors.strip()[:2000]}")
            if proc.returncode and proc.returncode != 0:
                result_parts.append(f"Exit code: {proc.returncode}")

            if not result_parts:
                return "Command executed successfully (no output)"
            return "\n\n".join(result_parts)

        except Exception as e:
            return f"Error executing command: {str(e)}"

    def _check_safety(self, command: str) -> str:
        """Check command against security rules. Returns error message or empty string."""
        # Check blocked patterns
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return f"Command contains blocked pattern"

        # Parse the command and check the base command
        try:
            # Handle pipes and chained commands
            parts = re.split(r'\s*[|;&]\s*', command)
            for part in parts:
                part = part.strip()
                if not part:
                    continue

                # Extract the base command
                tokens = shlex.split(part, posix=True)
                if not tokens:
                    continue

                base_cmd = tokens[0]

                # Handle 'env', 'time', 'nice' etc. prefix commands
                while base_cmd in ('env', 'time', 'nice', 'nohup', 'timeout') and len(tokens) > 1:
                    tokens = tokens[1:]
                    base_cmd = tokens[0]

                # Handle './' or '/' absolute paths
                if '/' in base_cmd:
                    base_cmd = base_cmd.split('/')[-1]

                if base_cmd not in ALLOWED_COMMANDS:
                    return f"Command '{base_cmd}' is not in the allowed commands list. Allowed: {', '.join(sorted(ALLOWED_COMMANDS)[:20])}..."

        except ValueError:
            # shlex parsing error - could be injection attempt
            return "Command could not be parsed safely"

        return ""

    def _is_safe_cwd(self, cwd: str) -> bool:
        """Check if working directory is safe."""
        import os
        safe_roots = ["/home/user", "/tmp"]
        try:
            resolved = os.path.realpath(cwd)
            return any(resolved.startswith(root) for root in safe_roots)
        except (ValueError, OSError):
            return False
