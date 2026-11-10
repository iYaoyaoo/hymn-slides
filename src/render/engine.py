"""统一引擎接口（v4 规范 F5）：放映/页面图片/全文文字走同一引擎链。

引擎能力分两级：
- render（页面图片导出 + 全文文字提取）
- show（原生放映控制：start/current_page/next/prev/end）

链上按优先级取第一个"可用且具备该能力"的引擎。macOS PowerPoint 只具备 show
（Mac 版无导出图片接口），render 回落 LibreOffice。
"""
from __future__ import annotations

from pathlib import Path

from src.render.engine_detect import (
    ENGINE_LIBREOFFICE,
    ENGINE_POWERPOINT,
    ENGINE_WPS,
    EngineCandidates,
    detect_engines,
)
from src.utils.logger import get_logger

logger = get_logger("engine")


class EngineUnsupported(Exception):
    """当前引擎不具备该能力（如 Mac PowerPoint 导出图片）。"""


class ShowSession:
    """一次原生放映会话的抽象（COM/AppleScript 实现见各自引擎）。"""

    def current_page(self) -> int:
        """当前页码（1 起）；放映已结束返回 0。"""
        raise NotImplementedError

    def next_page(self) -> None: ...
    def prev_page(self) -> None: ...
    def end(self) -> None: ...


class BaseEngine:
    name = "base"

    # ---------- 能力声明 ----------
    supports_render = False
    supports_show = False

    # ---------- render 能力 ----------
    def page_count(self, ppt: Path) -> int:
        raise EngineUnsupported(f"{self.name} 不支持页数导出")

    def export_page(self, ppt: Path, page_index: int, width_px: int, out_png: Path) -> Path:
        raise EngineUnsupported(f"{self.name} 不支持页面图片导出")

    def extract_texts(self, ppt: Path) -> list[tuple[int, str]]:
        raise EngineUnsupported(f"{self.name} 不支持文字提取")

    # ---------- show 能力 ----------
    def start_show(self, ppt: Path, screen_rect: tuple[int, int, int, int]) -> ShowSession:
        raise EngineUnsupported(f"{self.name} 不支持放映控制")


class EngineChain:
    """按优先级持有全部引擎实例；按能力路由。"""

    def __init__(self, engines: list[BaseEngine], candidates: EngineCandidates):
        self.engines = engines
        self.candidates = candidates

    @classmethod
    def autodetect(
        cls,
        ppt_path: str = "",
        wps_path: str = "",
        lo_path: str = "",
        lo_engine: BaseEngine | None = None,
    ) -> "EngineChain":
        cands = detect_engines(ppt_path, wps_path, lo_path)
        engines: list[BaseEngine] = []
        for info in cands.infos:
            if not info.available:
                continue
            if info.name == ENGINE_POWERPOINT:
                if info.supports_render:  # Windows COM
                    from src.render.com_engine import make_com_engine

                    engines.append(make_com_engine(ENGINE_POWERPOINT))
                else:  # macOS AppleScript
                    from src.render.as_engine import MacPptEngine

                    engines.append(MacPptEngine())
            elif info.name == ENGINE_WPS:
                from src.render.com_engine import make_com_engine

                engines.append(make_com_engine(ENGINE_WPS))
            elif info.name == ENGINE_LIBREOFFICE:
                engines.append(lo_engine or _make_lo_engine())
        return cls(engines, cands)

    # ---------- 能力路由 ----------

    def render_engine(self) -> BaseEngine | None:
        for e in self.engines:
            if e.supports_render:
                return e
        return None

    def show_engine(self) -> BaseEngine | None:
        for e in self.engines:
            if e.supports_show:
                return e
        return None

    def summary(self) -> list[str]:
        lines = []
        for info in self.candidates.infos:
            tag = "可用" if info.available else "不可用"
            caps = []
            if info.available and info.supports_render:
                caps.append("渲染")
            if info.available and info.supports_show:
                caps.append("放映")
            cap_text = "，能力：" + "/".join(caps) if caps else ""
            lines.append(f"引擎 {info.name}: {tag}（{info.detail}{cap_text}）")
        return lines


def _make_lo_engine() -> BaseEngine:
    from src.render.lo_engine import LibreOfficeEngine

    return LibreOfficeEngine()
