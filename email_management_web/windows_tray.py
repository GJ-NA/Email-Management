#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tray/status-bar integration for the packaged desktop app."""

from __future__ import annotations

from typing import Callable

from PIL import Image, ImageDraw
import pystray
from email_management_web.runtime import resource_path


class WindowsTrayApp:
    """Tray/status-bar app backed by pystray."""

    def __init__(self, tooltip: str, on_open: Callable[[], None], on_exit: Callable[[], None]):
        self.tooltip = tooltip[:127]
        self.on_open = on_open
        self.on_exit = on_exit
        self._icon = None

    def run(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("打开界面", self._handle_open, default=True),
            pystray.MenuItem("退出", self._handle_exit),
        )
        self._icon = pystray.Icon(
            "EmailManagement",
            self._build_icon(),
            self.tooltip,
            menu,
        )
        self._icon.run()

    def close(self) -> None:
        if self._icon is not None:
            self._icon.stop()

    def _handle_open(self, icon=None, item=None) -> None:
        self.on_open()

    def _handle_exit(self, icon=None, item=None) -> None:
        try:
            self.on_exit()
        finally:
            self.close()

    def _build_icon(self) -> Image.Image:
        icon_path = resource_path("assets", "email-management-icon.png")
        try:
            with Image.open(icon_path) as source:
                source = source.convert("RGBA")
                source.thumbnail((64, 64), Image.Resampling.LANCZOS)
                image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                position = ((64 - source.width) // 2, (64 - source.height) // 2)
                image.alpha_composite(source, position)
                return image
        except (FileNotFoundError, OSError):
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((10, 16, 54, 48), radius=5, outline=(26, 26, 26, 255), width=4)
            draw.line((11, 17, 32, 35, 53, 17), fill=(26, 26, 26, 255), width=4, joint="curve")
            return image
