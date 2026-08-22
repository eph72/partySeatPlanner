"""Small standard-library bridge for native macOS trackpad pinch gestures.

Tk 8.6 does not expose AppKit's ``magnifyWithEvent:`` through its documented
binding system.  This module adds that one responder method to the Tk content
view at runtime.  It is isolated here, optional, and silently falls back on
non-macOS systems; the main app also supports Command/Control + scroll zoom.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import platform
from typing import Callable


_BRIDGES: list["MacPinchBridge"] = []


class MacPinchBridge:
    """Attach AppKit magnification events to a Python callback."""

    def __init__(self, widget, callback: Callable[[float], None]) -> None:
        self.widget = widget
        self.callback = callback
        self.available = False
        self.error: str | None = None
        self._method_callback = None

        if platform.system() != "Darwin":
            self.error = "Native pinch is only available on macOS."
            return
        try:
            self._attach()
        except (AttributeError, OSError, RuntimeError, ValueError) as error:
            self.error = str(error)

    def _attach(self) -> None:
        self.widget.update_idletasks()
        drawable = int(self.widget.winfo_id())

        tk = ctypes.CDLL(self._loaded_tk_framework())
        tk.TkMacOSXGetRootControl.argtypes = [ctypes.c_ulong]
        tk.TkMacOSXGetRootControl.restype = ctypes.c_void_p
        view = tk.TkMacOSXGetRootControl(drawable)
        if not view:
            raise RuntimeError("Tk did not provide its native content view.")

        objc_path = ctypes.util.find_library("objc")
        if not objc_path:
            raise RuntimeError("The macOS Objective-C runtime was not found.")
        objc = ctypes.CDLL(objc_path)
        objc.object_getClass.argtypes = [ctypes.c_void_p]
        objc.object_getClass.restype = ctypes.c_void_p
        objc.objc_allocateClassPair.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        objc.objc_allocateClassPair.restype = ctypes.c_void_p
        objc.class_addMethod.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_char_p,
        ]
        objc.class_addMethod.restype = ctypes.c_bool
        objc.objc_registerClassPair.argtypes = [ctypes.c_void_p]
        objc.object_setClass.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        objc.object_setClass.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p

        original_class = objc.object_getClass(view)
        if not original_class:
            raise RuntimeError("Could not identify Tk's native view class.")
        subclass_name = f"PartySeatPlannerPinchView_{id(self):x}".encode("ascii")
        subclass = objc.objc_allocateClassPair(original_class, subclass_name, 0)
        if not subclass:
            raise RuntimeError("Could not create the native pinch responder.")

        magnification_selector = objc.sel_registerName(b"magnification")
        callback_type = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )
        message_double_type = ctypes.CFUNCTYPE(
            ctypes.c_double, ctypes.c_void_p, ctypes.c_void_p
        )
        message_double = message_double_type(
            ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        )

        def magnify(_native_self, _selector, event) -> None:
            try:
                amount = float(message_double(event, magnification_selector))
                if amount:
                    self.widget.after_idle(self.callback, amount)
            except Exception:
                # Exceptions must never cross an Objective-C callback boundary.
                return

        self._method_callback = callback_type(magnify)
        method_selector = objc.sel_registerName(b"magnifyWithEvent:")
        added = objc.class_addMethod(
            subclass,
            method_selector,
            ctypes.cast(self._method_callback, ctypes.c_void_p),
            b"v@:@",
        )
        if not added:
            raise RuntimeError("Could not register the native magnification handler.")
        objc.objc_registerClassPair(subclass)
        objc.object_setClass(view, subclass)

        self.available = True
        _BRIDGES.append(self)

    @staticmethod
    def _loaded_tk_framework() -> str:
        """Locate the exact Tk framework already loaded by this Python."""

        dyld = ctypes.CDLL(None)
        dyld._dyld_image_count.restype = ctypes.c_uint32
        dyld._dyld_get_image_name.argtypes = [ctypes.c_uint32]
        dyld._dyld_get_image_name.restype = ctypes.c_char_p
        for index in range(dyld._dyld_image_count()):
            raw_path = dyld._dyld_get_image_name(index)
            if not raw_path:
                continue
            path = raw_path.decode("utf-8", errors="replace")
            if "/Tk.framework/" in path and path.endswith("/Tk"):
                return path
        raise RuntimeError("The active Tk framework could not be located.")


def attach_pinch(widget, callback: Callable[[float], None]) -> MacPinchBridge:
    """Return a live bridge; inspect ``available`` for graceful fallback."""

    return MacPinchBridge(widget, callback)
