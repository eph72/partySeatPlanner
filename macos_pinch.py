"""Safe native macOS pinch support for Tk 8.6.

Tk 8.6 does not expose AppKit magnification gestures. A tiny Objective-C
bridge receives ``magnifyWithEvent:`` and writes each amount to a nonblocking
pipe. Tkinter watches the read end with its normal file-event machinery, so
Python is entered only through Tkinter's established, GIL-safe callback path.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import tkinter as tk
from typing import Callable


_BRIDGES: list["MacPinchBridge"] = []
_DOUBLE_SIZE = struct.calcsize("d")


class MacPinchBridge:
    """Attach AppKit magnification events to a Tk-safe Python callback."""

    def __init__(self, widget, callback: Callable[[float], None]) -> None:
        self.widget = widget
        self.callback = callback
        self.available = False
        self.error: str | None = None
        self._library = None
        self._view = None
        self._read_fd: int | None = None
        self._write_fd: int | None = None

        if platform.system() != "Darwin":
            self.error = "Native pinch is only available on macOS."
            return
        if tk.TkVersion < 8.6:
            self.error = f"Tk {tk.TkVersion:.1f} is too old for native pinch support."
            return
        try:
            self._attach()
        except (AttributeError, OSError, RuntimeError, ValueError) as error:
            self.error = str(error)
            self._cleanup()

    def _attach(self) -> None:
        self.widget.update_idletasks()
        drawable = int(self.widget.winfo_id())
        tk_path = self._loaded_framework("Tk")

        tk_framework = ctypes.CDLL(tk_path)
        tk_framework.TkMacOSXGetRootControl.argtypes = [ctypes.c_ulong]
        tk_framework.TkMacOSXGetRootControl.restype = ctypes.c_void_p
        self._view = tk_framework.TkMacOSXGetRootControl(drawable)
        if not self._view:
            raise RuntimeError("Tk did not provide its native content view.")

        library_path = self._build_bridge()
        self._library = ctypes.CDLL(str(library_path))
        self._library.PSPInstallPinchHandler.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._library.PSPInstallPinchHandler.restype = ctypes.c_int
        self._library.PSPTestPinch.argtypes = [ctypes.c_void_p, ctypes.c_double]
        self._library.PSPTestPinch.restype = ctypes.c_int

        self._read_fd, self._write_fd = os.pipe()
        os.set_blocking(self._read_fd, False)
        os.set_blocking(self._write_fd, False)
        self.widget.tk.createfilehandler(self._read_fd, tk.READABLE, self._on_pipe_readable)
        installed = self._library.PSPInstallPinchHandler(self._view, self._write_fd)
        if not installed:
            raise RuntimeError("The native magnification handler could not be installed.")

        self.available = True
        _BRIDGES.append(self)

    def _on_pipe_readable(self, _file_descriptor, _mask) -> None:
        """Receive coalesced native values through Tkinter's safe event path."""

        if self._read_fd is None:
            return
        chunks = bytearray()
        while True:
            try:
                chunk = os.read(self._read_fd, 4096)
            except BlockingIOError:
                break
            if not chunk:
                break
            chunks.extend(chunk)
            if len(chunk) < 4096:
                break
        complete_bytes = len(chunks) - (len(chunks) % _DOUBLE_SIZE)
        if not complete_bytes:
            return
        values = struct.iter_unpack("d", chunks[:complete_bytes])
        amount = sum(value[0] for value in values)
        if amount:
            self.callback(amount)

    def emit_test_pinch(self, amount: float = 0.1) -> bool:
        """Queue a native bridge event for launch-time smoke testing."""

        if not self.available or not self._library or not self._view:
            return False
        return bool(self._library.PSPTestPinch(self._view, float(amount)))

    def _cleanup(self) -> None:
        if self._read_fd is not None:
            try:
                self.widget.tk.deletefilehandler(self._read_fd)
            except (AttributeError, tk.TclError):
                pass
        for descriptor in (self._read_fd, self._write_fd):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        self._read_fd = self._write_fd = None

    @classmethod
    def _build_bridge(cls) -> Path:
        source = Path(__file__).with_name("macos_pinch_bridge.m")
        if not source.exists():
            raise RuntimeError("macos_pinch_bridge.m is missing.")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
        output_folder = Path(__file__).resolve().parent / "__pycache__"
        output_folder.mkdir(exist_ok=True)
        output = output_folder / f"macos_pinch_{platform.machine()}_{digest}.dylib"
        if output.exists():
            return output

        clang = shutil.which("clang")
        if not clang:
            raise RuntimeError("Apple's clang compiler is required for native pinch support.")
        temporary = output.with_suffix(".building.dylib")
        command = [
            clang,
            "-dynamiclib",
            "-fobjc-arc",
            "-O2",
            "-Wall",
            "-Wextra",
            "-framework",
            "Cocoa",
            str(source),
            "-o",
            str(temporary),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode:
            temporary.unlink(missing_ok=True)
            detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown error"
            raise RuntimeError(f"Could not build native pinch support: {detail}")
        os.replace(temporary, output)
        return output

    @staticmethod
    def _loaded_framework(name: str) -> str:
        """Locate the exact framework already loaded by this Python process."""

        dyld = ctypes.CDLL(None)
        dyld._dyld_image_count.restype = ctypes.c_uint32
        dyld._dyld_get_image_name.argtypes = [ctypes.c_uint32]
        dyld._dyld_get_image_name.restype = ctypes.c_char_p
        marker = f"/{name}.framework/"
        for index in range(dyld._dyld_image_count()):
            raw_path = dyld._dyld_get_image_name(index)
            if not raw_path:
                continue
            path = raw_path.decode("utf-8", errors="replace")
            if marker in path and path.endswith(f"/{name}"):
                return path
        raise RuntimeError(f"The active {name} framework could not be located.")


def attach_pinch(widget, callback: Callable[[float], None]) -> MacPinchBridge:
    """Return a live bridge; inspect ``available`` for graceful fallback."""

    return MacPinchBridge(widget, callback)
