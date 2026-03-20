import asyncio
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any

from gi.repository import GObject, Gtk
from utils.config import Config
from utils.file import File as file
from utils.packages import PackageIndexer
from utils.process import Process as process
from utils.requests import Requests as requests

__all__ = ['file', 'requests', 'process', 'PackageIndexer', 'Config']


def task(fn: callable):
    if not iscoroutinefunction(fn):
        raise TypeError("Must be an async function")

    @wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.create_task(fn(*args, **kwargs))

    return wrapper


class EnumMap:  # string -> Enum
    halign = Gtk.Align
    valign = Gtk.Align
    orientation = Gtk.Orientation
    justify = Gtk.Justification
    selection_mode = Gtk.SelectionMode

    @classmethod
    def map(cls, prop: str, value: str) -> Any | None:
        enum = getattr(cls, prop, None)

        if enum is None:
            return

        return getattr(enum, value)


class PropMap:

    @classmethod
    def apply(cls, widget: Gtk.Widget, key: str, value: Any) -> bool:
        handler = getattr(cls, key, None)

        if not callable(handler):
            return False

        handler(widget, value)
        return True

    @staticmethod
    def size_request(widget: Gtk.Widget, value: int | list[int]):
        if isinstance(value, int):
            widget.set_size_request(value, value)
            return

        elif isinstance(value, (list, tuple)):
            if len(value) == 1:
                v = value[0]
                widget.set_size_request(v, v)
                return

            elif len(value) == 2:
                h, w = value
                widget.set_size_request(w, h)
                return

        raise ValueError("size_request must contain 1 or 2 values")

    @staticmethod
    def margin(widget: Gtk.Widget, value: int | list[int]):
        if isinstance(value, int):
            widget.set_margin_top(value)
            widget.set_margin_bottom(value)
            widget.set_margin_start(value)
            widget.set_margin_end(value)
            return

        elif isinstance(value, (list, tuple)):
            if len(value) == 1:
                v = value[0]
                widget.set_margin_top(v)
                widget.set_margin_bottom(v)
                widget.set_margin_start(v)
                widget.set_margin_end(v)
                return

            elif len(value) == 2:
                v, h = value
                widget.set_margin_top(v)
                widget.set_margin_bottom(v)
                widget.set_margin_start(h)
                widget.set_margin_end(h)
                return

            elif len(value) == 4:
                t, r, b, l = value
                widget.set_margin_top(t)
                widget.set_margin_end(r)
                widget.set_margin_bottom(b)
                widget.set_margin_start(l)
                return

        raise ValueError("margin must contain 1, 2 or 4 values")

    def children(widget: Gtk.Widget, value: Gtk.Widget | list[Gtk.Widget]):
        ...


def asztalify(ctor: Gtk.Widget, **kwargs):
    widget = ctor(visible=kwargs.get('visible', True))

    setup = kwargs.pop('setup', None)

    for key, value in kwargs.items():
        if key.startswith('on_notify'):

            def on_notified(this: Gtk.Widget, pspec: GObject.ParamSpec):
                value(this, getattr(this.props, pspec.get_name()))

            prop = key.removeprefix('on_notify_').replace('_', '-')
            widget.connect('notify::' + prop, on_notified)

        elif key.startswith('on_'):
            signal = key.removeprefix('on_').replace('_', '-')

            widget.connect(signal, value)
        elif PropMap.apply(widget, key, value):
            continue
        elif (enum := EnumMap.map(key, value)) is not None:
            setattr(widget.props, key, enum)
        else:
            setattr(widget.props, key, value)

    if setup:
        setup(widget)

    return widget
