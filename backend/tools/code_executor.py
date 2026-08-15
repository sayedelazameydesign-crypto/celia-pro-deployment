"""
celia.pro Code Execution Tool
===============================
Execute code in a restricted sandbox with security checks.
"""

from typing import Dict, Any
import asyncio
import sys
import io
import re
import logging
import tempfile
import os

from tools.base import BaseTool
from core.tool_security import RiskLevel

logger = logging.getLogger(__name__)


# Patterns that could escape the sandbox
SANDBOX_ESCAPE_PATTERNS = [
    r"__class__",
    r"__bases__",
    r"__subclasses__",
    r"__mro__",
    r"__import__",
    r"__builtins__",
    r"globals\s*\(\s*\)",
    r"locals\s*\(\s*\)",
    r"eval\s*\(",
    r"exec\s*\(",
    r"compile\s*\(",
    r"getattr\s*\(",
    r"setattr\s*\(",
    r"delattr\s*\(",
    r"os\.",
    r"sys\.",
    r"subprocess",
    r"import\s+os",
    r"import\s+sys",
    r"import\s+subprocess",
    r"from\s+os",
    r"from\s+sys",
    r"from\s+subprocess",
    r"open\s*\(",
    r"__file__",
    r"pdb",
    r"ctypes",
    r"importlib",
]


class CodeExecutorTool(BaseTool):
    """Execute code in a restricted sandbox."""

    name = "execute_code"
    description = "Execute Python code and return the output. Use this for calculations, data processing, analysis, and generating code solutions. The code runs in a restricted sandbox."
    category = "execution"
    risk_level = RiskLevel.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds (default: 30, max: 60)",
                "default": 30
            },
            "language": {
                "type": "string",
                "enum": ["python", "javascript"],
                "description": "Programming language of the code",
                "default": "python"
            }
        },
        "required": ["code"]
    }

    # Safe builtins - explicitly curated
    SAFE_BUILTINS = {
        "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
        "bytes": bytes, "chr": chr, "complex": complex, "dict": dict,
        "divmod": divmod, "enumerate": enumerate, "filter": filter,
        "float": float, "format": format, "frozenset": frozenset,
        "hash": hash, "hex": hex, "int": int, "isinstance": isinstance,
        "issubclass": issubclass, "iter": iter, "len": len, "list": list,
        "map": map, "max": max, "min": min, "next": next, "oct": oct,
        "ord": ord, "pow": pow, "print": print, "range": range,
        "repr": repr, "reversed": reversed, "round": round, "set": set,
        "slice": slice, "sorted": sorted, "str": str, "sum": sum,
        "tuple": tuple, "zip": zip,
        "True": True, "False": False, "None": None,
        # NO __import__, NO open, NO exec, NO eval, NO compile
    }

    # Safe modules - explicitly curated
    SAFE_MODULES = {}

    @classmethod
    def _init_safe_modules(cls):
        """Initialize safe modules with restricted access."""
        import math
        import json as _json
        import datetime as _datetime
        import collections as _collections
        import itertools as _itertools
        import functools as _functools
        import re as _re
        import string as _string
        import textwrap as _textwrap
        import decimal as _decimal
        import fractions as _fractions
        import statistics as _statistics
        import random as _random

        cls.SAFE_MODULES = {
            "math": math,
            "json": _json,
            "datetime": _datetime,
            "collections": _collections,
            "itertools": _itertools,
            "functools": _functools,
            "re": _re,
            "string": _string,
            "textwrap": _textwrap,
            "decimal": _decimal,
            "fractions": _fractions,
            "statistics": _statistics,
            "random": _random,
        }

    def __init__(self):
        if not self.SAFE_MODULES:
            self._init_safe_modules()

    async def execute(self, code: str, timeout: int = 30, language: str = "python", **kwargs) -> str:
        """Execute code with security checks."""
        # Enforce timeout limits
        timeout = min(max(timeout, 1), 60)

        if language == "python":
            return await self._execute_python(code, timeout)
        elif language == "javascript":
            return await self._execute_javascript(code, timeout)
        return f"Unsupported language: {language}. Supported: python, javascript"

    def _check_safety(self, code: str) -> str:
        """Check code for sandbox escape attempts. Returns error message or empty string."""
        for pattern in SANDBOX_ESCAPE_PATTERNS:
            match = re.search(pattern, code)
            if match:
                return f"Code contains disallowed operation: '{match.group()}'"
        return ""

    async def _execute_python(self, code: str, timeout: int) -> str:
        """Execute Python code in a sandboxed environment."""
        # Pre-execution safety check
        safety_error = self._check_safety(code)
        if safety_error:
            return f"Safety Check Failed: {safety_error}"

        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, self._run_python, code),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return f"Error: Code execution timed out after {timeout} seconds"

    def _run_python(self, code: str) -> str:
        """Run Python code synchronously in a restricted environment."""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured_out = io.StringIO()
        captured_err = io.StringIO()

        try:
            sys.stdout = captured_out
            sys.stderr = captured_err

            # Create restricted environment - NO import, NO file access
            env = {
                "__builtins__": dict(self.SAFE_BUILTINS),
            }
            # Add safe modules
            env.update(self.SAFE_MODULES)

            # Execute
            exec(code, env)

            stdout = captured_out.getvalue()
            stderr = captured_err.getvalue()

            result = ""
            if stdout:
                # Limit output size
                if len(stdout) > 10000:
                    stdout = stdout[:10000] + "\n[Output truncated at 10000 chars]"
                result += f"Output:\n{stdout}\n"
            if stderr:
                result += f"Warnings:\n{stderr[:1000]}\n"
            if not result:
                result = "Code executed successfully (no output)"
            return result.strip()

        except SyntaxError as e:
            return f"Syntax Error: {e}"
        except Exception as e:
            # Don't leak traceback details
            return f"Execution Error: {type(e).__name__}: {str(e)}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    async def _execute_javascript(self, code: str, timeout: int) -> str:
        """Execute JavaScript using Node.js in a restricted environment."""
        try:
            # Wrap in a sandbox
            wrapped_code = f"""
            const vm = require('vm');
            const sandbox = {{ console: {{ log: console.log, error: console.error }} }};
            try {{
                vm.runInNewContext({repr(code)}, sandbox, {{ timeout: {timeout * 1000} }});
            }} catch(e) {{
                console.error(e.message);
            }}
            """
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, dir='/tmp') as f:
                f.write(wrapped_code)
                f.flush()
                tmp_path = f.name

            try:
                proc = await asyncio.create_subprocess_exec(
                    'node', '--max-old-space-size=128', tmp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                result = ""
                if stdout:
                    result += f"Output:\n{stdout.decode()[:10000]}\n"
                if stderr:
                    result += f"Errors:\n{stderr.decode()[:2000]}\n"
                return result.strip() or "Code executed successfully"
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except asyncio.TimeoutError:
            return f"Error: Code execution timed out after {timeout} seconds"
        except FileNotFoundError:
            return "Error: Node.js is not installed"
        except Exception as e:
            return f"Error: {str(e)}"
