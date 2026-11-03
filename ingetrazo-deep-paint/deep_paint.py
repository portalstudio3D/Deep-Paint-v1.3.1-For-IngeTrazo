# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo Community Contributors.
"""Deep Material Painter for IngeTrazo.

Allows painting faces and assigning materials directly to geometry inside
groups and components without having to open / edit each container.
Includes:
- Deep raycast picking into nested groups & component instances
- Complete Texture & UV projection support (_texture_commands)
- Instant synchronization with IngeTrazo's native Paint tool (B) eyedropper (Alt+Clic)
- Crisp native QToolBar with Deep Paint activation and Options menu
- Live Eyedropper sampling texture, color, and material tags inside containers
- Live hover highlighting of target faces inside containers
- Single-face, similar-in-group, coplanar, and reset/clear modes
- Native undo/redo integration (Ctrl+Z)
- Ultra-responsive, narrow-friendly side tray dock panel (<=240px)
"""
from __future__ import annotations

import os
import sys
import math
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import Qt, QPoint, QPointF, QSize, QTimer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QCursor,
    QIcon,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
    QVector3D,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QDockWidget,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from tools.base import Tool
from core.i18n import tr

try:
    from core.history import (
        Command,
        CompoundCommand,
        SetFaceColorCommand,
        SetFaceMaterialTagCommand,
        SetFaceTextureCommand,
        SetFaceOpacityCommand,
        SetFaceBackCommand,
    )
except ImportError:
    Command = object  # type: ignore
    CompoundCommand = None  # type: ignore
    SetFaceColorCommand = None  # type: ignore
    SetFaceMaterialTagCommand = None  # type: ignore
    SetFaceTextureCommand = None  # type: ignore
    SetFaceOpacityCommand = None  # type: ignore
    SetFaceBackCommand = None  # type: ignore

try:
    from tools.paint import (
        PaintTool,
        _face_plane,
        _same_plane,
        _texture_commands,
        DEFAULT_FACE_COLOR,
    )
except ImportError:
    PaintTool = None  # type: ignore
    _face_plane = None  # type: ignore
    _same_plane = None  # type: ignore
    _texture_commands = None  # type: ignore
    DEFAULT_FACE_COLOR = (0.8, 0.8, 0.8)

DISPLAY_NAME = "Deep Paint"
KEY = "deep_paint"
VERSION = "1.3.1"
TOOLBAR_NAME = "ingetrazo_deep_paint_toolbar"


# ---------------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------------

def _clean_mat_name(mat: Any) -> str:
    """Extracts a clean human-readable material name (e.g. 'brick_clay').

    Prevents raw Python object repr strings like 'Material(name=...)' from
    polluting UI labels and forcing layouts wide.
    """
    if not mat:
        return ""
    if hasattr(mat, "name"):
        val = getattr(mat, "name")
        if isinstance(val, str) and val:
            return val
    if isinstance(mat, dict):
        val = mat.get("name") or mat.get("mat")
        if isinstance(val, str) and val:
            return val
    s = str(mat).strip()
    if s.startswith("Material(") and "name=" in s:
        idx = s.find("name=")
        if idx != -1:
            rest = s[idx + 5:]
            q = rest[0] if rest and rest[0] in ("'", '"') else None
            if q:
                end_q = rest.find(q, 1)
                if end_q != -1:
                    return rest[1:end_q]
    return s


def is_dark_ui(widget: Optional[QWidget] = None) -> bool:
    """Detects whether IngeTrazo is running in dark theme mode."""
    try:
        from views.theme import is_dark
        return bool(is_dark())
    except Exception:
        pass
    try:
        app = QApplication.instance()
        w = widget or (app.activeWindow() if app else None)
        if w:
            return w.palette().color(QPalette.Window).value() < 128
    except Exception:
        pass
    return False


def make_deep_paint_icon(active: bool = False, dark: bool = False) -> QIcon:
    """Draws a crisp 64x64 vector icon: isometric container cube with painted front face."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    ink = QColor("#e0e0e0" if dark else "#2c3e50")
    accent = QColor("#f37329" if active else "#1e88e5")

    # Outer highlighted frame when active
    if active:
        p.setPen(QPen(QColor("#f37329"), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QBrush(QColor(243, 115, 41, 25)))
        p.drawRoundedRect(4, 4, 56, 56, 6, 6)

    # 1. Top Face
    p.setPen(QPen(ink, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QBrush(QColor(accent.red(), accent.green(), accent.blue(), 35 if active else 20)))
    poly_top = QPolygonF([QPointF(32, 11), QPointF(53, 22), QPointF(32, 33), QPointF(11, 22)])
    p.drawPolygon(poly_top)

    # 2. Left Face (Target face painted in deep material)
    p.setPen(QPen(ink, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QBrush(accent))
    poly_left = QPolygonF([QPointF(11, 22), QPointF(32, 33), QPointF(32, 53), QPointF(11, 42)])
    p.drawPolygon(poly_left)

    # 3. Right Face
    p.setPen(QPen(ink, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QBrush(QColor(accent.red(), accent.green(), accent.blue(), 55 if active else 30)))
    poly_right = QPolygonF([QPointF(32, 33), QPointF(53, 22), QPointF(53, 42), QPointF(32, 53)])
    p.drawPolygon(poly_right)

    # Center divide line
    center_color = QColor("#ffffff" if active else "#ff9800")
    p.setPen(QPen(center_color, 2.0, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(32, 33, 32, 53)

    # Glossy highlight dot
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(255, 255, 255, 180)))
    p.drawEllipse(QPointF(19, 34), 3, 3)

    p.end()
    return QIcon(pix)


def make_deep_paint_options_icon(dark: bool = False) -> QIcon:
    """Draws a crisp 64x64 vector artist palette with 4 distinct material swatch dots."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    ink = QColor("#e0e0e0" if dark else "#2c3e50")

    p.setPen(QPen(ink, 2.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QBrush(QColor(40, 40, 45, 180) if dark else QColor(255, 255, 255, 220)))

    path = QPainterPath()
    path.moveTo(32, 10)
    path.cubicTo(52, 10, 56, 30, 48, 44)
    path.cubicTo(44, 52, 36, 54, 28, 52)
    path.cubicTo(22, 50, 20, 44, 24, 38)
    path.cubicTo(26, 34, 24, 30, 18, 32)
    path.cubicTo(10, 34, 8, 20, 20, 12)
    path.cubicTo(24, 10, 28, 10, 32, 10)
    path.closeSubpath()
    p.drawPath(path)

    p.setPen(QPen(ink, 2.0, Qt.SolidLine))
    p.setBrush(QBrush(QColor(0, 0, 0, 0)))
    p.drawEllipse(QPointF(23, 41), 4.5, 4.5)

    colors = ["#e53935", "#fdd835", "#1e88e5", "#43a047"]
    positions = [(26, 18), (37, 16), (46, 25), (44, 36)]
    for (cx, cy), c_hex in zip(positions, colors):
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(c_hex)))
        p.drawEllipse(QPointF(cx, cy), 4, 4)

    p.end()
    return QIcon(pix)


# ---------------------------------------------------------------------------
# Custom Undoable Commands
# ---------------------------------------------------------------------------

class ResetFaceMaterialCommand(Command):
    """Reverts face materials to default, letting them inherit the group material."""

    def __init__(self, faces: list) -> None:
        self._faces = list(faces)
        self._old: list[dict] = []

    def do(self, scene) -> None:
        self._old = []
        for f in self._faces:
            self._old.append({
                "color": f.attrs.get("color"),
                "mat": f.attrs.get("mat"),
                "texture": f.attrs.get("texture"),
                "uvw": f.attrs.get("uvw"),
                "opacity": f.attrs.get("opacity"),
                "back": f.attrs.get("back"),
            })
            f.attrs.pop("color", None)
            f.attrs.pop("mat", None)
            f.attrs.pop("texture", None)
            f.attrs.pop("uvw", None)
            f.attrs.pop("opacity", None)
            f.attrs.pop("back", None)
        self._dirty(scene)

    def undo(self, scene) -> None:
        for f, old in zip(self._faces, self._old):
            for k, v in old.items():
                if v is not None:
                    f.attrs[k] = v
                else:
                    f.attrs.pop(k, None)
        self._dirty(scene)

    def _dirty(self, scene) -> None:
        dirty_fn = getattr(scene, "_dirty_group_chunks", None)
        if callable(dirty_fn):
            dirty_fn(*self._faces)
        if hasattr(scene, "version"):
            scene.version += 1


# ---------------------------------------------------------------------------
# Geometry Helpers
# ---------------------------------------------------------------------------

def _calc_face_plane(face) -> Optional[tuple]:
    """Calculates normal vector and plane distance (n, d) for a face."""
    if _face_plane is not None:
        try:
            return _face_plane(face)
        except Exception:
            pass

    loop = getattr(face, "loop", [])
    if len(loop) < 3:
        return None
    p0 = loop[0].position
    p1 = loop[1].position
    p2 = loop[2].position
    v1 = p1 - p0
    v2 = p2 - p0
    n = QVector3D.crossProduct(v1, v2)
    if n.lengthSquared() > 1e-10:
        norm = n.normalized()
        d = QVector3D.dotProduct(norm, p0)
        return norm, d
    return None


def _find_similar_faces_in_group(group, target_face) -> list:
    """Finds all faces in the group mesh sharing the same initial color/material/texture."""
    if not hasattr(group, "mesh") or not group.mesh:
        return [target_face]

    tgt_mat = target_face.attrs.get("mat")
    tgt_col = target_face.attrs.get("color")
    tgt_tex = target_face.attrs.get("texture")

    similar = []
    for f in group.mesh.faces:
        if (
            f.attrs.get("mat") == tgt_mat
            and f.attrs.get("color") == tgt_col
            and f.attrs.get("texture") == tgt_tex
        ):
            similar.append(f)
    return similar or [target_face]


def _find_coplanar_connected_faces(group, target_face, tol: float = 1e-4) -> list:
    """Finds coplanar connected faces in the group."""
    if not hasattr(group, "mesh") or not group.mesh:
        return [target_face]

    plane = _calc_face_plane(target_face)
    if plane is None:
        return [target_face]
    target_n, target_d = plane

    coplanar_faces = []
    for f in group.mesh.faces:
        fp = _calc_face_plane(f)
        if fp is None:
            continue
        fn, fd = fp
        if abs(QVector3D.dotProduct(fn, target_n) - 1.0) < tol and abs(fd - target_d) < tol:
            coplanar_faces.append(f)

    return coplanar_faces or [target_face]


# ---------------------------------------------------------------------------
# Deep Paint Tool (subclass of tools.base.Tool)
# ---------------------------------------------------------------------------

class DeepPaintTool(Tool):
    """Viewport tool to directly click and paint faces inside groups/components."""

    name = DISPLAY_NAME
    shortcut = "Ctrl+Shift+B"
    description = "Paint faces inside groups and components with project materials & textures"
    uses_snap = False

    def __init__(self, panel: Optional[Any] = None, toolbar: Optional[Any] = None) -> None:
        super().__init__()
        self.panel = panel
        self.toolbar = toolbar
        self._sampling = False

        # Independent internal material state
        self._current_color = QColor(195, 150, 100)
        self._current_mat_name = ""
        self._current_texture: Optional[dict] = None
        self._current_texture_plane: Optional[tuple] = None
        self._current_opacity: float = 1.0
        self._mode: str = "single"

    def set_sampling(self, sampling: bool) -> None:
        self._sampling = sampling

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        if self.panel and hasattr(self.panel, "set_mode"):
            self.panel.set_mode(mode)
        if self.toolbar and hasattr(self.toolbar, "set_mode"):
            self.toolbar.set_mode(mode)

    def get_mode(self) -> str:
        return self._mode

    def get_active_material_description(self) -> str:
        """Returns a user-friendly description of the active material & texture."""
        parts = []
        if self._current_mat_name:
            parts.append(f"'{self._current_mat_name}'")
        if self._current_texture:
            tex_path = self._current_texture.get("path") if isinstance(self._current_texture, dict) else None
            if tex_path:
                parts.append(f"Texture ({os.path.basename(str(tex_path))})")
            else:
                parts.append("Texture")
        if self._current_color:
            parts.append(f"#{self._current_color.name()[1:].upper()}")
        return " + ".join(parts) if parts else "Défaut"

    def sync_from_paint_tool(self) -> bool:
        """Automatically pulls the active material, texture, and color from IngeTrazo's PaintTool (B)."""
        if PaintTool is None:
            return False

        tex = getattr(PaintTool, "current_texture", None)
        col = getattr(PaintTool, "current_color", None)
        mat = getattr(PaintTool, "current_material", None)
        opacity = getattr(PaintTool, "current_opacity", 1.0)
        plane = getattr(PaintTool, "current_texture_plane", None)

        # Pull attributes if mat is a Material instance
        if hasattr(mat, "texture") and tex is None:
            tex = getattr(mat, "texture")
        if hasattr(mat, "color") and col is None:
            col = getattr(mat, "color")
        if hasattr(mat, "opacity") and (opacity is None or opacity == 1.0):
            op = getattr(mat, "opacity")
            if op is not None:
                opacity = op

        self._current_texture = tex
        self._current_texture_plane = plane
        self._current_opacity = float(opacity if opacity is not None else 1.0)
        self._current_mat_name = _clean_mat_name(mat)

        if col is not None:
            if isinstance(col, QColor):
                self._current_color = col
            elif isinstance(col, (tuple, list)) and len(col) >= 3:
                r, g, b = [int(round(float(c) * 255)) for c in col[:3]]
                self._current_color = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

        # Keep panel in sync if it exists
        if self.panel is not None:
            self.panel._current_texture = self._current_texture
            self.panel._current_texture_plane = self._current_texture_plane
            self.panel._current_color = self._current_color
            self.panel._current_mat_name = self._current_mat_name
            self.panel._current_opacity = self._current_opacity
            if hasattr(self.panel, "edit_mat_name"):
                self.panel.edit_mat_name.setText(self._current_mat_name)
            self.panel._update_swatch_display()

        return True

    def on_activate(self, viewport) -> None:
        viewport.setCursor(QCursor(Qt.CrossCursor))

        # Automatic sync with PaintTool (B) whenever Deep Paint is activated
        self.sync_from_paint_tool()

        desc = self.get_active_material_description()
        viewport.flash_status(
            f"Deep Paint Actif : {desc} | Clic = peindre, Alt+Clic = pipette, Shift+Clic = similaire",
            3500
        )
        if self.toolbar:
            self.toolbar.update_tool_state(True)
        if self.panel:
            self.panel.update_tool_state(True)
            self.panel.refresh_project_materials()

    def on_deactivate(self, viewport) -> None:
        viewport.set_hover(None, None)
        viewport.unsetCursor()
        if self.toolbar:
            self.toolbar.update_tool_state(False)
        if self.panel:
            self.panel.update_tool_state(False)

    def on_hover(self, ctx) -> None:
        vp = ctx.viewport
        x = int(ctx.screen.x())
        y = int(ctx.screen.y())

        placement = None
        face = None
        if hasattr(vp, "pick_face_placement"):
            face, placement = vp.pick_face_placement(x, y)
        elif hasattr(vp, "pick_face_any"):
            face, placement = vp.pick_face_any(x, y)

        vp.set_hover(face, placement)

        if self.panel:
            self.panel.update_hover_info(face, placement)

    def on_click(self, ctx) -> None:
        vp = ctx.viewport
        x = int(ctx.screen.x())
        y = int(ctx.screen.y())

        face, placement = None, None
        if hasattr(vp, "pick_face_placement"):
            face, placement = vp.pick_face_placement(x, y)
        elif hasattr(vp, "pick_face_any"):
            face, placement = vp.pick_face_any(x, y)

        if face is None:
            return

        owner = getattr(placement, "group", None) or placement

        # Check Eyedropper / Sampling mode (or Alt held)
        alt_pressed = bool(ctx.modifiers & Qt.AltModifier)
        if self._sampling or alt_pressed:
            self._sample_face(face, owner, vp)
            if self._sampling:
                self.set_sampling(False)
                if self.panel:
                    self.panel.set_eyedropper_active(False)
            return

        # Paint action
        shift_pressed = bool(ctx.modifiers & Qt.ShiftModifier)
        mode = self._mode
        if shift_pressed and mode == "single":
            mode = "similar"

        self.apply_paint(vp, face, owner, mode)

    def _sample_face(self, face, owner, vp) -> None:
        """Sample material, texture, UVW, and color from face or its parent owner."""
        src = dict(face.attrs)

        if not src.get("color") and not src.get("texture") and not src.get("mat") and owner:
            g_mat = getattr(owner, "material", None)
            if isinstance(g_mat, dict):
                src.update(g_mat)

        mat_name = _clean_mat_name(src.get("mat"))
        scene_mats = getattr(vp.scene, "materials", {})
        if mat_name and mat_name in scene_mats:
            mat_obj = scene_mats[mat_name]
            if hasattr(mat_obj, "face_attrs"):
                m_attrs = mat_obj.face_attrs()
                for k in ("color", "texture", "opacity"):
                    if src.get(k) is None and m_attrs.get(k) is not None:
                        src[k] = m_attrs[k]
            elif isinstance(mat_obj, dict):
                for k in ("color", "texture", "opacity"):
                    if src.get(k) is None and mat_obj.get(k) is not None:
                        src[k] = mat_obj[k]

        tex = src.get("texture")
        col = src.get("color")
        opacity = src.get("opacity", 1.0)
        plane = _calc_face_plane(face) if tex else None

        # Update Deep Paint internal state
        self._current_texture = tex
        self._current_texture_plane = plane
        self._current_opacity = float(opacity if opacity is not None else 1.0)
        self._current_mat_name = mat_name
        if col and len(col) >= 3:
            r, g, b = [int(round(float(c) * 255)) for c in col[:3]]
            self._current_color = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

        # Sync to IngeTrazo's native PaintTool (B)
        if PaintTool:
            PaintTool.current_texture = tex
            PaintTool.current_texture_plane = plane
            if col:
                PaintTool.current_color = col[:3] if isinstance(col, (tuple, list)) else col
            PaintTool.current_material = mat_name or ""
            PaintTool.current_opacity = opacity
            PaintTool.current_is_default = False

        # Sync to panel & tray
        if self.panel:
            self.panel.set_sampled_material(
                color=col,
                texture=tex,
                texture_plane=plane,
                mat_name=mat_name,
                opacity=opacity,
            )
            self.panel.sync_to_native_tray()

        details = []
        if mat_name:
            details.append(f"Matériau '{mat_name}'")
        if tex:
            details.append("Texture")
        if col:
            r, g, b = [int(round(float(c) * 255)) for c in col[:3]]
            details.append(f"RGB({r},{g},{b})")

        desc = " + ".join(details) if details else "Défaut"
        owner_name = getattr(owner, "name", "Face") if owner else "Face"
        vp.flash_status(f"Pipette : {desc} prélevé sur {owner_name} !", 3000)

    def apply_paint(self, vp, target_face, owner, mode: Optional[str] = None) -> None:
        """Applies texture, material tag, and color to target face(s) inside the group."""
        if mode is None:
            mode = self._mode

        if mode == "reset":
            faces = [target_face]
            if owner and hasattr(owner, "mesh"):
                faces = _find_similar_faces_in_group(owner, target_face)
            cmd = ResetFaceMaterialCommand(faces)
            vp.history.execute(cmd)
            vp.flash_status(f"Matériau réinitialisé sur {len(faces)} face(s)", 2500)
            vp.update()
            return

        if mode == "similar" and owner:
            faces = _find_similar_faces_in_group(owner, target_face)
        elif mode == "coplanar" and owner:
            faces = _find_coplanar_connected_faces(owner, target_face)
        else:
            faces = [target_face]

        cmds = []
        tex = self._current_texture
        plane = self._current_texture_plane
        color = self._current_color
        rgb_float = (color.redF(), color.greenF(), color.blueF())
        mat_name = self._current_mat_name.strip()
        opacity = self._current_opacity

        # 3. Texture
        if tex and SetFaceTextureCommand is not None:
            if _texture_commands is not None:
                try:
                    tex_cmds = _texture_commands(faces, tex, plane)
                    cmds.extend(tex_cmds)
                except Exception:
                    cmds.append(SetFaceTextureCommand(faces, tex))
            else:
                cmds.append(SetFaceTextureCommand(faces, tex))
        elif not tex and SetFaceTextureCommand is not None:
            cmds.append(SetFaceTextureCommand(faces, None))

        # 4. Material tag
        if mat_name and SetFaceMaterialTagCommand is not None:
            scene_mats = getattr(vp.scene, "materials", {})
            mat_dict = scene_mats.get(mat_name)
            cmds.append(SetFaceMaterialTagCommand(faces, mat_name, mat_dict))
        elif not mat_name and SetFaceMaterialTagCommand is not None:
            cmds.append(SetFaceMaterialTagCommand(faces, "", None))

        # 5. Base Color
        if SetFaceColorCommand is not None:
            cmds.append(SetFaceColorCommand(faces, rgb_float))

        # 6. Opacity
        if opacity < 1.0 and SetFaceOpacityCommand is not None:
            cmds.append(SetFaceOpacityCommand(faces, opacity))

        if not cmds:
            for f in faces:
                f.attrs["color"] = rgb_float
                if tex:
                    f.attrs["texture"] = tex
                else:
                    f.attrs.pop("texture", None)
                if mat_name:
                    f.attrs["mat"] = mat_name
                else:
                    f.attrs.pop("mat", None)
                f.attrs["opacity"] = opacity
            vp.notify_scene_changed()
            vp.update()
            return

        if len(cmds) == 1:
            vp.history.execute(cmds[0])
        elif CompoundCommand is not None:
            vp.history.execute(CompoundCommand(cmds))
        else:
            for c in cmds:
                vp.history.execute(c)

        dirty_fn = getattr(vp.scene, "_dirty_group_chunks", None)
        if callable(dirty_fn):
            dirty_fn(*faces)

        vp.update()
        owner_label = getattr(owner, "name", "Groupe") if owner else "Groupe"
        desc = f"'{mat_name}'" if mat_name else ("Texture" if tex else f"#{color.name()[1:].upper()}")
        vp.flash_status(f"{len(faces)} face(s) de '{owner_label}' peinte(s) avec {desc} !", 2500)


# ---------------------------------------------------------------------------
# Deep Paint Native QToolBar (Minimal & Ergonomic)
# ---------------------------------------------------------------------------

class DeepPaintToolbar(QToolBar):
    """Native QToolBar for Deep Material Painter, dockable, floatable, and minimal."""

    def __init__(self, window, tool: DeepPaintTool, panel: Any) -> None:
        super().__init__("Deep Paint", window)
        self.window = window
        self.tool = tool
        self.panel = panel
        self.setObjectName(TOOLBAR_NAME)
        self.setMovable(True)
        self.setFloatable(True)
        self.setAllowedAreas(Qt.AllToolBarAreas)

        px = 28
        try:
            from views.icons import toolbar_icon_px
            px = toolbar_icon_px()
        except Exception:
            pass
        self.setIconSize(QSize(px, px))
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setToolTip("Deep Paint : Glisser la poignée pour déplacer ou ancrer cette barre d'outils.")

        dark = is_dark_ui(self.window)

        # 1. Action Deep Paint
        self.act_tool = QAction(make_deep_paint_icon(False, dark), "Deep Paint", self)
        self.act_tool.setCheckable(True)
        self.act_tool.setChecked(False)
        self.act_tool.setToolTip(
            "Deep Paint (Ctrl+Shift+B)\n"
            "Peindre des faces et textures directement à l'intérieur des groupes et composants.\n"
            "(Synchronisé automatiquement avec la pipette de Peinture B)"
        )
        self.act_tool.setStatusTip("Activer l'outil Deep Paint (peindre directement dans les conteneurs)")
        self.act_tool.triggered.connect(self._on_toggle_tool)
        self.addAction(self.act_tool)

        # 2. Bouton Options
        self.btn_options = QToolButton(self)
        self.btn_options.setText("Options")
        self.btn_options.setIcon(make_deep_paint_options_icon(dark))
        self.btn_options.setToolTip("Options & Réglages Deep Paint (Mode, Pipette, Nuancier, Matériaux)")
        self.btn_options.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.btn_options.setPopupMode(QToolButton.InstantPopup)

        self._build_options_menu()
        self.addWidget(self.btn_options)

        try:
            from views.icons import style_overflow_button
            style_overflow_button(self)
        except Exception:
            pass

    def _build_options_menu(self) -> None:
        menu = QMenu(self)

        self.mode_group = QActionGroup(menu)
        self.mode_group.setExclusive(True)

        self.act_mode_single = QAction("🎯 Face cliquée uniquement", menu)
        self.act_mode_single.setCheckable(True)
        self.act_mode_single.setChecked(True)
        self.act_mode_single.triggered.connect(lambda: self.tool.set_mode("single"))
        self.mode_group.addAction(self.act_mode_single)
        menu.addAction(self.act_mode_single)

        self.act_mode_similar = QAction("🔗 Faces similaires du groupe (Shift+Clic)", menu)
        self.act_mode_similar.setCheckable(True)
        self.act_mode_similar.triggered.connect(lambda: self.tool.set_mode("similar"))
        self.mode_group.addAction(self.act_mode_similar)
        menu.addAction(self.act_mode_similar)

        self.act_mode_coplanar = QAction("📐 Faces coplanaires connectées", menu)
        self.act_mode_coplanar.setCheckable(True)
        self.act_mode_coplanar.triggered.connect(lambda: self.tool.set_mode("coplanar"))
        self.mode_group.addAction(self.act_mode_coplanar)
        menu.addAction(self.act_mode_coplanar)

        self.act_mode_reset = QAction("🧹 Réinitialiser au matériau du groupe", menu)
        self.act_mode_reset.setCheckable(True)
        self.act_mode_reset.triggered.connect(lambda: self.tool.set_mode("reset"))
        self.mode_group.addAction(self.act_mode_reset)
        menu.addAction(self.act_mode_reset)

        menu.addSeparator()

        act_eyedropper = menu.addAction("🧪 Pipette (Échantillonner avec Alt+Clic)")
        act_eyedropper.triggered.connect(self._activate_eyedropper)

        act_sync = menu.addAction("⚡ Synchroniser avec l'outil Peinture (B)")
        act_sync.triggered.connect(self._force_sync_from_paint)

        act_color = menu.addAction("🎨 Choisir une couleur...")
        act_color.triggered.connect(self._open_color_picker)

        self.menu_project_mats = menu.addMenu("📦 Matériaux du document")
        self.menu_project_mats.aboutToShow.connect(self._populate_project_materials_menu)

        menu.addSeparator()

        act_tray = menu.addAction("📑 Afficher le panneau dans le plateau")
        act_tray.triggered.connect(self._show_panel_in_tray)

        act_help = menu.addAction("💡 Aide & Raccourcis...")
        act_help.triggered.connect(self._show_help_dialog)

        self.btn_options.setMenu(menu)

    def _on_toggle_tool(self, checked: bool) -> None:
        viewport = getattr(self.window, "viewport", None)
        if not viewport:
            return
        if checked:
            self.tool.sync_from_paint_tool()
            viewport.set_active_tool(self.tool)
        else:
            if getattr(viewport, "active_tool", None) is self.tool:
                viewport.set_active_tool(None)

    def _activate_eyedropper(self) -> None:
        viewport = getattr(self.window, "viewport", None)
        if viewport:
            self.tool.set_sampling(True)
            viewport.set_active_tool(self.tool)
            viewport.flash_status("Pipette armée : Cliquez sur une face pour prélever sa matière", 3500)

    def _force_sync_from_paint(self) -> None:
        self.tool.sync_from_paint_tool()
        viewport = getattr(self.window, "viewport", None)
        if viewport:
            desc = self.tool.get_active_material_description()
            viewport.flash_status(f"Synchronisé avec Peinture (B) : {desc}", 2500)

    def _open_color_picker(self) -> None:
        dlg = QColorDialog(self.tool._current_color, self.window)
        dlg.setWindowTitle("Deep Paint - Choisir une couleur")
        if dlg.exec():
            selected = dlg.selectedColor()
            self.tool._current_color = selected
            self.tool._current_texture = None
            self.tool._current_texture_plane = None
            if PaintTool:
                PaintTool.current_color = (selected.redF(), selected.greenF(), selected.blueF())
                PaintTool.current_material = self.tool._current_mat_name
                PaintTool.current_is_default = False
            if self.panel:
                self.panel.set_current_color(selected)
            viewport = getattr(self.window, "viewport", None)
            if viewport:
                viewport.flash_status(f"Couleur #{selected.name()[1:].upper()} sélectionnée", 2000)

    def _populate_project_materials_menu(self) -> None:
        self.menu_project_mats.clear()
        viewport = getattr(self.window, "viewport", None)
        scene = getattr(viewport, "scene", None) if viewport else None
        mats = getattr(scene, "materials", {}) if scene else {}

        if not mats:
            act_none = self.menu_project_mats.addAction("(Aucun matériau défini dans le projet)")
            act_none.setEnabled(False)
            return

        for name in sorted(mats.keys(), key=str):
            mat_obj = mats[name]
            tex = getattr(mat_obj, "texture", None) if hasattr(mat_obj, "texture") else (
                mat_obj.get("texture") if isinstance(mat_obj, dict) else None
            )
            clean_name = _clean_mat_name(name)
            label = f"📦 {clean_name}" + (" [Texture]" if tex else "")
            act = self.menu_project_mats.addAction(label)
            act.triggered.connect(lambda _, n=name: self._select_project_material(n))

    def _select_project_material(self, name: str) -> None:
        if self.panel:
            self.panel.set_material_from_project(name)
        else:
            self.tool._current_mat_name = _clean_mat_name(name)
            viewport = getattr(self.window, "viewport", None)
            if viewport:
                viewport.flash_status(f"Matériau '{self.tool._current_mat_name}' sélectionné", 2000)

    def _show_panel_in_tray(self) -> None:
        if self.panel:
            self.panel.dock_to_tray()

    def _show_help_dialog(self) -> None:
        QMessageBox.information(
            self.window,
            "Aide - Deep Material Painter",
            "🎨 <b>Deep Material Painter</b> permet d'appliquer textures et matières "
            "directement sur des faces imbriquées dans des groupes et composants.<br><br>"
            "<b>Raccourcis & Utilisation :</b><br>"
            "• <b>Clic gauche</b> : Peindre la face ciblée dans le groupe<br>"
            "• <b>Alt + Clic</b> : Pipette (capture texture, matière et UV)<br>"
            "• <b>Peinture (B) + Alt+Clic</b> : La pipette de l'outil Peinture standard (B) "
            "est automatiquement synchronisée avec Deep Paint !<br>"
            "• <b>Shift + Clic</b> : Peindre toutes les faces similaires dans le groupe<br>"
            "• <b>Ctrl + Z</b> : Annuler (Undo transactionnel complet)"
        )

    def set_mode(self, mode: str) -> None:
        if mode == "reset":
            self.act_mode_reset.setChecked(True)
        elif mode == "similar":
            self.act_mode_similar.setChecked(True)
        elif mode == "coplanar":
            self.act_mode_coplanar.setChecked(True)
        else:
            self.act_mode_single.setChecked(True)

    def update_tool_state(self, active: bool) -> None:
        dark = is_dark_ui(self.window)
        self.act_tool.setChecked(active)
        self.act_tool.setIcon(make_deep_paint_icon(active, dark))
        self.btn_options.setIcon(make_deep_paint_options_icon(dark))


# ---------------------------------------------------------------------------
# Deep Paint Dock Panel (Ultra-Responsive & Narrow Side-Tray Widget)
# ---------------------------------------------------------------------------

class DeepPaintPanel(QWidget):
    """Narrow-friendly, responsive side-tray panel fitting smoothly in 200px - 280px docks."""

    PRESETS = [
        ("Blanc", QColor(245, 245, 245)),
        ("Gris Béton", QColor(140, 145, 145)),
        ("Anthracite", QColor(45, 48, 52)),
        ("Chêne Clair", QColor(195, 150, 100)),
        ("Noyer Foncé", QColor(90, 60, 40)),
        ("Terre Cuite", QColor(185, 80, 55)),
        ("Brique Rouge", QColor(150, 50, 40)),
        ("Verre Teinté", QColor(140, 200, 220)),
        ("Bleu Cobalt", QColor(40, 90, 170)),
        ("Vert Sauge", QColor(120, 145, 115)),
        ("Laiton Doré", QColor(210, 170, 70)),
        ("Noir Mat", QColor(25, 25, 25)),
    ]

    def __init__(self, viewport, tool: Optional[DeepPaintTool] = None, parent=None) -> None:
        super().__init__(parent)
        self.viewport = viewport
        self.tool = tool or DeepPaintTool(panel=self)
        self.tool.panel = self
        self.toolbar: Optional[DeepPaintToolbar] = None
        self.dock: Optional[QDockWidget] = None

        self._current_color = QColor(195, 150, 100)
        self._current_mat_name = ""
        self._current_texture: Optional[dict] = None
        self._current_texture_plane: Optional[tuple] = None
        self._current_opacity: float = 1.0
        self._eyedropper_active = False

        self.setMinimumWidth(0)
        self._build_ui()
        self._apply_theme()
        QTimer.singleShot(200, self.refresh_project_materials)

    def sizeHint(self) -> QSize:
        return QSize(250, 480)

    def minimumSizeHint(self) -> QSize:
        return QSize(160, 200)

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Responsive Scroll Area (prevents horizontal expansion)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMinimumWidth(0)

        content_widget = QWidget()
        content_widget.setMinimumWidth(0)
        content_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(8)

        # --- 1. Outils & Activation ---
        tool_box = QGroupBox("Outils")
        tool_layout = QVBoxLayout(tool_box)
        tool_layout.setContentsMargins(6, 6, 6, 6)
        tool_layout.setSpacing(5)

        self.btn_toggle_tool = QPushButton("🎯 Activer Deep Paint")
        self.btn_toggle_tool.setCheckable(True)
        self.btn_toggle_tool.setStyleSheet(
            "QPushButton { font-weight: bold; padding: 5px; } "
            "QPushButton:checked { background-color: #2e7d32; color: white; }"
        )
        self.btn_toggle_tool.clicked.connect(self._toggle_tool_activation)
        tool_layout.addWidget(self.btn_toggle_tool)

        eyedropper_row = QHBoxLayout()
        eyedropper_row.setSpacing(4)
        self.btn_eyedropper = QPushButton("🧪 Pipette")
        self.btn_eyedropper.setCheckable(True)
        self.btn_eyedropper.setToolTip("Cliquez sur une face pour capturer sa matière et sa texture (Alt+Clic)")
        self.btn_eyedropper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_eyedropper.clicked.connect(self._toggle_eyedropper)
        eyedropper_row.addWidget(self.btn_eyedropper)

        self.btn_sync_paint = QPushButton("⚡ Sync (B)")
        self.btn_sync_paint.setToolTip("Récupère instantanément la matière/texture active dans l'outil Peinture standard (B)")
        self.btn_sync_paint.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_sync_paint.clicked.connect(self.sync_from_paint_tool)
        eyedropper_row.addWidget(self.btn_sync_paint)
        tool_layout.addLayout(eyedropper_row)

        main_layout.addWidget(tool_box)

        # --- 2. Matériaux du Projet ---
        proj_box = QGroupBox("Matériaux du Projet")
        proj_layout = QVBoxLayout(proj_box)
        proj_layout.setContentsMargins(6, 6, 6, 6)
        proj_layout.setSpacing(4)

        combo_row = QHBoxLayout()
        combo_row.setSpacing(4)
        self.combo_project_mats = QComboBox()
        self.combo_project_mats.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.combo_project_mats.setMinimumContentsLength(6)
        self.combo_project_mats.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.combo_project_mats.setMinimumWidth(40)
        self.combo_project_mats.currentIndexChanged.connect(self._on_project_mat_selected)
        combo_row.addWidget(self.combo_project_mats)

        self.btn_refresh_mats = QPushButton("🔄")
        self.btn_refresh_mats.setFixedSize(26, 24)
        self.btn_refresh_mats.setToolTip("Actualiser la liste des matériaux du document")
        self.btn_refresh_mats.clicked.connect(self.refresh_project_materials)
        combo_row.addWidget(self.btn_refresh_mats)
        proj_layout.addLayout(combo_row)

        main_layout.addWidget(proj_box)

        # --- 3. Matière / Texture Active ---
        mat_box = QGroupBox("Matière Active")
        mat_layout = QVBoxLayout(mat_box)
        mat_layout.setContentsMargins(6, 6, 6, 6)
        mat_layout.setSpacing(6)

        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(6)
        self.lbl_swatch = QLabel()
        self.lbl_swatch.setFixedSize(40, 36)
        self.lbl_swatch.setFrameShape(QFrame.Box)
        self.lbl_swatch.setAlignment(Qt.AlignCenter)
        swatch_row.addWidget(self.lbl_swatch)

        swatch_info = QVBoxLayout()
        swatch_info.setSpacing(1)
        self.lbl_mat_status = QLabel("Couleur pleine")
        self.lbl_mat_status.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.lbl_mat_status.setWordWrap(True)
        self.lbl_mat_status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_mat_status.setMinimumWidth(40)
        swatch_info.addWidget(self.lbl_mat_status)

        self.lbl_tex_details = QLabel("Aucune texture")
        self.lbl_tex_details.setStyleSheet("font-size: 10px; color: #888;")
        self.lbl_tex_details.setWordWrap(True)
        self.lbl_tex_details.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_tex_details.setMinimumWidth(40)
        swatch_info.addWidget(self.lbl_tex_details)
        swatch_row.addLayout(swatch_info)

        self.btn_pick_color = QPushButton("Couleur...")
        self.btn_pick_color.setFixedWidth(64)
        self.btn_pick_color.clicked.connect(self._open_color_dialog)
        swatch_row.addWidget(self.btn_pick_color)
        mat_layout.addLayout(swatch_row)

        # Nom
        tag_row = QHBoxLayout()
        tag_row.setSpacing(4)
        lbl_tag = QLabel("Nom :")
        lbl_tag.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        tag_row.addWidget(lbl_tag)
        self.edit_mat_name = QLineEdit()
        self.edit_mat_name.setPlaceholderText("Ex: Bois_Chene, Brique...")
        self.edit_mat_name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.edit_mat_name.setMinimumWidth(40)
        self.edit_mat_name.textChanged.connect(self._on_mat_name_changed)
        tag_row.addWidget(self.edit_mat_name)
        mat_layout.addLayout(tag_row)

        # Nuancier compact (Grille de 6 colonnes × 2 lignes)
        presets_label = QLabel("Nuancier rapide :")
        presets_label.setStyleSheet("font-size: 10px; opacity: 0.8;")
        mat_layout.addWidget(presets_label)

        presets_grid = QGridLayout()
        presets_grid.setSpacing(3)
        presets_grid.setContentsMargins(0, 2, 0, 2)
        for idx, (name, col) in enumerate(self.PRESETS):
            r = idx // 6
            c = idx % 6
            btn = QPushButton()
            btn.setFixedSize(26, 22)
            btn.setToolTip(f"{name} ({col.name()})")
            btn.setStyleSheet(f"background-color: {col.name()}; border: 1px solid #555; border-radius: 3px;")
            btn.clicked.connect(lambda _, c_col=col, n_name=name: self.set_current_color(c_col, mat_name=n_name))
            presets_grid.addWidget(btn, r, c)
        mat_layout.addLayout(presets_grid)

        main_layout.addWidget(mat_box)

        # --- 4. Portée / Mode de Peinture ---
        mode_box = QGroupBox("Portée d'Application")
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.setContentsMargins(6, 6, 6, 6)
        mode_layout.setSpacing(3)

        self.radio_single = QRadioButton("🎯 Face cliquée uniquement")
        self.radio_single.setChecked(True)
        self.radio_single.toggled.connect(lambda checked: checked and self.tool.set_mode("single"))
        mode_layout.addWidget(self.radio_single)

        self.radio_similar = QRadioButton("🔗 Faces similaires (Shift+Clic)")
        self.radio_similar.toggled.connect(lambda checked: checked and self.tool.set_mode("similar"))
        mode_layout.addWidget(self.radio_similar)

        self.radio_coplanar = QRadioButton("📐 Faces coplanaires connectées")
        self.radio_coplanar.toggled.connect(lambda checked: checked and self.tool.set_mode("coplanar"))
        mode_layout.addWidget(self.radio_coplanar)

        self.radio_reset = QRadioButton("🧹 Réinitialiser au défaut")
        self.radio_reset.toggled.connect(lambda checked: checked and self.tool.set_mode("reset"))
        mode_layout.addWidget(self.radio_reset)

        main_layout.addWidget(mode_box)

        # --- 5. Inspecteur de Face ---
        info_box = QGroupBox("Inspecteur Cible (Survol)")
        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(6, 6, 6, 6)
        info_layout.setSpacing(2)

        self.lbl_target_group = QLabel("Groupe : —")
        self.lbl_target_group.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.lbl_target_group.setWordWrap(True)
        self.lbl_target_group.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_target_group.setMinimumWidth(30)
        info_layout.addWidget(self.lbl_target_group)

        self.lbl_target_face = QLabel("Face : (survolez le modèle 3D)")
        self.lbl_target_face.setStyleSheet("font-size: 10px;")
        self.lbl_target_face.setWordWrap(True)
        self.lbl_target_face.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_target_face.setMinimumWidth(30)
        info_layout.addWidget(self.lbl_target_face)

        self.lbl_target_material = QLabel("Matière : —")
        self.lbl_target_material.setStyleSheet("font-size: 10px;")
        self.lbl_target_material.setWordWrap(True)
        self.lbl_target_material.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_target_material.setMinimumWidth(30)
        info_layout.addWidget(self.lbl_target_material)

        main_layout.addWidget(info_box)

        main_layout.addStretch()

        # Aide raccourcis
        hint = QLabel(
            "💡 Raccourcis :\n"
            "• Clic : Peindre la face dans le groupe\n"
            "• Alt + Clic : Pipette directe\n"
            "• Peinture (B) + Alt+Clic : Sync automatique !\n"
            "• Shift + Clic : Peindre tout le similaire\n"
            "• Ctrl + Z : Annuler"
        )
        hint.setStyleSheet("font-size: 10px; color: #888; padding: 2px;")
        hint.setWordWrap(True)
        hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        hint.setMinimumWidth(30)
        main_layout.addWidget(hint)

        scroll.setWidget(content_widget)
        outer_layout.addWidget(scroll)

        self._update_swatch_display()

    def set_dock(self, dock: QDockWidget) -> None:
        self.dock = dock

    def dock_to_tray(self) -> None:
        """Affiche le panneau dans le plateau d'onglets latéral."""
        if not self.dock:
            return
        win = getattr(self.viewport, "window", lambda: None)()
        tray = getattr(win, "tray", None) if win else None
        if win and tray:
            try:
                win.tabifyDockWidget(tray, self.dock)
            except Exception:
                pass
        self.dock.show()
        self.dock.raise_()
        self.viewport.flash_status("Deep Paint affiché dans le plateau latéral", 2500)

    def set_mode(self, mode: str) -> None:
        if mode == "reset":
            self.radio_reset.setChecked(True)
        elif mode == "similar":
            self.radio_similar.setChecked(True)
        elif mode == "coplanar":
            self.radio_coplanar.setChecked(True)
        else:
            self.radio_single.setChecked(True)

    def _apply_theme(self) -> None:
        is_dark = self.palette().color(QPalette.Window).value() < 128
        border_col = "#555" if is_dark else "#ccc"
        self.lbl_swatch.setStyleSheet(f"border: 1px solid {border_col}; border-radius: 3px;")

    # ---- Gestion des Matériaux du Projet ----

    def refresh_project_materials(self) -> None:
        """Populates the combo box with materials defined in scene.materials."""
        scene = getattr(self.viewport, "scene", None)
        if not scene:
            return

        mats = getattr(scene, "materials", {})
        current_data = self.combo_project_mats.currentData()

        self.combo_project_mats.blockSignals(True)
        self.combo_project_mats.clear()
        self.combo_project_mats.addItem("— Matériaux du Projet —", None)

        found_names = set()
        if isinstance(mats, dict):
            for name, mat in sorted(mats.items(), key=lambda x: str(x[0])):
                found_names.add(name)
                tex = getattr(mat, "texture", None) if hasattr(mat, "texture") else (
                    mat.get("texture") if isinstance(mat, dict) else None
                )
                clean_name = _clean_mat_name(name)
                tag = f"📦 {clean_name}" + (" (Texture)" if tex else "")
                self.combo_project_mats.addItem(tag, name)

        if current_data and current_data in found_names:
            idx = self.combo_project_mats.findData(current_data)
            if idx >= 0:
                self.combo_project_mats.setCurrentIndex(idx)

        self.combo_project_mats.blockSignals(False)

    def _on_project_mat_selected(self, index: int) -> None:
        if index <= 0:
            return
        mat_name = self.combo_project_mats.currentData()
        if not mat_name:
            return
        self.set_material_from_project(mat_name)

    def set_material_from_project(self, mat_name: str) -> None:
        """Loads a material from scene.materials into Deep Paint."""
        scene = getattr(self.viewport, "scene", None)
        if not scene:
            return
        mats = getattr(scene, "materials", {})
        mat = mats.get(mat_name)
        if not mat:
            return

        if hasattr(mat, "face_attrs"):
            attrs = mat.face_attrs()
        elif isinstance(mat, dict):
            attrs = dict(mat)
        else:
            attrs = {
                "mat": getattr(mat, "name", mat_name),
                "color": getattr(mat, "color", None),
                "texture": getattr(mat, "texture", None),
                "opacity": getattr(mat, "opacity", 1.0),
            }

        col = attrs.get("color")
        tex = attrs.get("texture")
        opacity = attrs.get("opacity", 1.0)

        clean_name = _clean_mat_name(mat_name)
        self._current_mat_name = clean_name
        self.edit_mat_name.setText(clean_name)
        self._current_texture = tex
        self._current_texture_plane = None
        self._current_opacity = opacity

        if col and len(col) >= 3:
            r, g, b = [int(round(float(c) * 255)) for c in col[:3]]
            self._current_color = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

        self._update_swatch_display()

        # Update Tool instance
        self.tool._current_mat_name = self._current_mat_name
        self.tool._current_texture = self._current_texture
        self.tool._current_texture_plane = None
        self.tool._current_opacity = self._current_opacity
        self.tool._current_color = self._current_color

        # Sync to IngeTrazo's PaintTool
        if PaintTool:
            PaintTool.current_material = clean_name
            PaintTool.current_texture = tex
            PaintTool.current_texture_plane = None
            if col:
                PaintTool.current_color = col[:3] if isinstance(col, (tuple, list)) else col
            PaintTool.current_opacity = opacity
            PaintTool.current_is_default = False

        self.sync_to_native_tray()

        if not self.btn_toggle_tool.isChecked():
            self.btn_toggle_tool.setChecked(True)
            self._toggle_tool_activation(True)

    def sync_from_paint_tool(self) -> None:
        """Pulls the active material & texture from IngeTrazo's native PaintTool."""
        self.tool.sync_from_paint_tool()
        self._current_texture = self.tool._current_texture
        self._current_texture_plane = self.tool._current_texture_plane
        self._current_opacity = self.tool._current_opacity
        self._current_mat_name = self.tool._current_mat_name
        self._current_color = self.tool._current_color
        self.edit_mat_name.setText(self._current_mat_name)

        self._update_swatch_display()
        desc = self._current_mat_name or ("Texture" if self._current_texture else "Couleur")
        self.viewport.flash_status(f"Deep Paint synchronisé ({desc})", 2500)
        self.refresh_project_materials()

    def sync_to_native_tray(self) -> None:
        """Refreshes IngeTrazo's native materials dock tray."""
        win = getattr(self.viewport, "window", lambda: None)()
        tray = getattr(win, "tray", None)
        mat_panel = getattr(tray, "materials", None)
        if mat_panel and hasattr(mat_panel, "sync_from_paint"):
            try:
                mat_panel.sync_from_paint()
            except Exception:
                pass

    # ---- Contrôles & État ----

    def _toggle_tool_activation(self, active: bool) -> None:
        if active:
            self.tool.sync_from_paint_tool()
            if hasattr(self.viewport, "set_active_tool"):
                self.viewport.set_active_tool(self.tool)
        else:
            if hasattr(self.viewport, "set_active_tool") and getattr(self.viewport, "active_tool", None) is self.tool:
                self.viewport.set_active_tool(None)

    def _toggle_eyedropper(self, active: bool) -> None:
        self._eyedropper_active = active
        self.tool.set_sampling(active)
        if active:
            self.btn_toggle_tool.setChecked(True)
            self._toggle_tool_activation(True)
            self.viewport.flash_status(
                "Pipette Armée : Cliquez sur une face dans un groupe pour capturer sa matière",
                3000
            )

    def set_eyedropper_active(self, active: bool) -> None:
        self._eyedropper_active = active
        self.btn_eyedropper.setChecked(active)
        self.tool.set_sampling(active)

    def _open_color_dialog(self) -> None:
        dlg = QColorDialog(self._current_color, self)
        dlg.setWindowTitle("Choisir une couleur")
        if dlg.exec():
            self._current_texture = None
            self._current_texture_plane = None
            self.set_current_color(dlg.selectedColor())

    def _update_swatch_display(self) -> None:
        if not hasattr(self, "lbl_mat_status") or not hasattr(self, "lbl_tex_details") or not hasattr(self, "lbl_swatch"):
            return

        clean_name = _clean_mat_name(self._current_mat_name)

        tex_path = self._current_texture.get("path") if isinstance(self._current_texture, dict) else None
        if tex_path and os.path.exists(str(tex_path)):
            pm = QPixmap(str(tex_path))
            if not pm.isNull():
                self.lbl_swatch.setPixmap(
                    pm.scaled(self.lbl_swatch.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                )
                self.lbl_mat_status.setText(clean_name or "Texture Image")
                sw = self._current_texture.get("sw", 1.0)
                sh = self._current_texture.get("sh", 1.0)
                self.lbl_tex_details.setText(f"{os.path.basename(str(tex_path))} ({sw:.2f}m × {sh:.2f}m)")
                return

        self.lbl_swatch.setPixmap(QPixmap())
        col_hex = self._current_color.name()
        self.lbl_swatch.setStyleSheet(
            f"background-color: {col_hex}; border: 1px solid #555; border-radius: 3px;"
        )
        if clean_name:
            self.lbl_mat_status.setText(clean_name)
        else:
            self.lbl_mat_status.setText(f"Couleur {col_hex.upper()}")

        if self._current_texture:
            self.lbl_tex_details.setText("Texture procédurale")
        else:
            self.lbl_tex_details.setText("Couleur unie (sans texture)")

    def _on_mat_name_changed(self, text: str) -> None:
        self._current_mat_name = _clean_mat_name(text.strip())
        self.tool._current_mat_name = self._current_mat_name

    def set_current_color(self, color: QColor, mat_name: Optional[str] = None) -> None:
        self._current_color = color
        self.tool._current_color = color
        if mat_name is not None:
            clean_name = _clean_mat_name(mat_name)
            self._current_mat_name = clean_name
            self.tool._current_mat_name = clean_name
            self.edit_mat_name.setText(clean_name)
        self._update_swatch_display()

        if PaintTool:
            PaintTool.current_color = (color.redF(), color.greenF(), color.blueF())
            PaintTool.current_material = self._current_mat_name
            PaintTool.current_is_default = False

        if not self.btn_toggle_tool.isChecked():
            self.btn_toggle_tool.setChecked(True)
            self._toggle_tool_activation(True)

    def set_sampled_material(
        self,
        color: Optional[Any],
        texture: Optional[dict],
        texture_plane: Optional[tuple],
        mat_name: Optional[str],
        opacity: float = 1.0
    ) -> None:
        """Sets full material state sampled from eyedropper."""
        self._current_texture = texture
        self._current_texture_plane = texture_plane
        self._current_opacity = opacity
        clean_name = _clean_mat_name(mat_name)
        self._current_mat_name = clean_name
        self.edit_mat_name.setText(clean_name)

        if color and len(color) >= 3:
            r, g, b = [int(round(float(c) * 255)) for c in color[:3]]
            self._current_color = QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

        self._update_swatch_display()
        self.refresh_project_materials()

    def get_current_color(self) -> QColor:
        return self._current_color

    def get_current_texture(self) -> Optional[dict]:
        return self._current_texture

    def get_current_texture_plane(self) -> Optional[tuple]:
        return self._current_texture_plane

    def get_current_material_name(self) -> str:
        return self._current_mat_name

    def get_current_opacity(self) -> float:
        return self._current_opacity

    def update_tool_state(self, active: bool) -> None:
        self.btn_toggle_tool.setChecked(active)
        self.btn_toggle_tool.setText("🎯 Tool ACTIF (Désactiver)" if active else "🎯 Activer Deep Paint")

    def update_hover_info(self, face, placement) -> None:
        if face is None:
            self.lbl_target_face.setText("Face : (aucune)")
            self.lbl_target_group.setText("Groupe : —")
            self.lbl_target_material.setText("Matière : —")
            return

        owner = getattr(placement, "group", None) or placement
        owner_name = getattr(owner, "name", "Maillage") if owner else "Maillage"
        verts_count = len(getattr(face, "loop", []))

        col = face.attrs.get("color")
        mat = _clean_mat_name(face.attrs.get("mat"))
        tex = face.attrs.get("texture")

        mat_info = []
        if mat:
            mat_info.append(f"'{mat}'")
        if tex:
            mat_info.append("Texture")
        if col:
            r, g, b = [int(round(float(c) * 255)) for c in col[:3]]
            mat_info.append(f"RGB({r},{g},{b})")

        if not mat_info:
            mat_info.append("Défaut (hérité)")

        self.lbl_target_group.setText(f"Groupe : {owner_name}")
        self.lbl_target_face.setText(f"Face #{id(face) % 10000} ({verts_count} sommets)")
        self.lbl_target_material.setText(f"Matière : {' + '.join(mat_info)}")


# ---------------------------------------------------------------------------
# Setup & Registration Hook
# ---------------------------------------------------------------------------

_plugin_panel: Optional[DeepPaintPanel] = None
_plugin_tool: Optional[DeepPaintTool] = None
_plugin_toolbar: Optional[DeepPaintToolbar] = None


def setup(app: Any) -> None:
    """Plugin entry point invoked when IngeTrazo initializes."""
    global _plugin_panel, _plugin_tool, _plugin_toolbar

    viewport = getattr(app, "viewport", None)
    win = getattr(app, "window", getattr(app, "_window", None))
    if viewport is None and win and hasattr(win, "viewport"):
        viewport = win.viewport

    if viewport is None:
        return

    _plugin_tool = DeepPaintTool()
    _plugin_panel = DeepPaintPanel(viewport, tool=_plugin_tool)
    _plugin_tool.panel = _plugin_panel

    # 1. Register Tool in IngeTrazo Tool registry
    if hasattr(app, "register_tool"):
        app.register_tool(_plugin_tool)

    # 2. Add side tray panel (dockable in tray, compact title, not floating)
    dock = None
    if hasattr(app, "add_panel"):
        dock = app.add_panel(DISPLAY_NAME, _plugin_panel)
        _plugin_panel.set_dock(dock)
        tray = getattr(win, "tray", None) if win else None
        if win and tray and dock:
            try:
                win.tabifyDockWidget(tray, dock)
            except Exception:
                pass
        if dock:
            dock.setMinimumWidth(180)
            if hasattr(dock, "widget") and dock.widget():
                dock.widget().setMinimumWidth(0)
            dock.hide()

    # 3. Create native QToolBar matching MultiView
    if win:
        _plugin_toolbar = DeepPaintToolbar(win, tool=_plugin_tool, panel=_plugin_panel)
        _plugin_tool.toolbar = _plugin_toolbar
        _plugin_panel.toolbar = _plugin_toolbar
        win.addToolBar(Qt.TopToolBarArea, _plugin_toolbar)

    # 4. Add to Extensions menu
    menu = app.add_menu("Deep Paint") if hasattr(app, "add_menu") else None
    if menu is not None:
        act_tool = menu.addAction(
            f"Activer {DISPLAY_NAME} ({_plugin_tool.shortcut})",
            lambda: viewport.set_active_tool(_plugin_tool)
        )
        act_tool.setStatusTip("Peindre des faces et textures directement à l'intérieur des groupes")

        menu.addSeparator()
        act_sync = menu.addAction("⚡ Synchroniser avec l'outil Peinture (B)", _plugin_tool.sync_from_paint_tool)
        act_sync.setStatusTip("Récupère le matériau/texture actif dans l'outil Peinture standard")

        if _plugin_toolbar:
            toggle_tb = _plugin_toolbar.toggleViewAction()
            toggle_tb.setText("Afficher la barre d'outils Deep Paint")
            menu.addAction(toggle_tb)

        if dock:
            act_panel = menu.addAction("📌 Afficher le panneau dans le plateau", _plugin_panel.dock_to_tray)
            act_panel.setStatusTip("Afficher Deep Paint dans le plateau d'onglets latéral")

    print(f"[{KEY}] {DISPLAY_NAME} v{VERSION} chargé avec barre d'outils native et synchronisation de Peinture (B).")
