"""Test bootstrap.

The integration's real package ``__init__.py`` imports Home Assistant, which
isn't installed in a bare test environment. The pure-math modules (``calc`` and
``const``) have no HA dependency, so we load them under a lightweight ``hb``
package whose ``__init__`` is never executed. Relative imports inside ``calc``
(``from .const import ...``) then resolve against this stand-in package.
"""

import importlib.util
import sys
import types
from pathlib import Path

_BASE = Path(__file__).resolve().parents[1] / "custom_components" / "hydrobalance"

if "hb" not in sys.modules:
    _pkg = types.ModuleType("hb")
    _pkg.__path__ = [str(_BASE)]
    sys.modules["hb"] = _pkg
    for _name in ("const", "calc"):
        _spec = importlib.util.spec_from_file_location(f"hb.{_name}", _BASE / f"{_name}.py")
        _mod = importlib.util.module_from_spec(_spec)
        sys.modules[f"hb.{_name}"] = _mod
        _spec.loader.exec_module(_mod)
        setattr(_pkg, _name, _mod)
