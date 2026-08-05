from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable
import uuid

from fontTools.ttLib import TTFont

from .project_store import ProjectStore
from .subtitles import CaptionCue, caption_cues_from_payload


CAPTION_MAX_WIDTH_RATIO = 0.8
CAPTION_MAX_LINES = 1
CAPTION_BOTTOM_OFFSET_RATIO = 0.2
CAPTION_TRANSFORM_Y = -0.6
CAPTION_REFERENCE_FONT_SIZE = 15.0
CAPTION_REFERENCE_MAX_EM = 14.0
CAPTION_MIN_SLICE_US = 80_000
_BREAK_CHARS = set("，,、：:。！？!?；;")
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class CaptionLayoutReviewRequired(ValueError):
    """The selected font cannot safely produce the requested one-line cues."""


@dataclass(frozen=True)
class FontMetrics:
    path: Path
    units_per_em: int
    cmap: dict[int, str]
    advances: dict[str, tuple[int, int]]

    @classmethod
    def load(cls, path: str | Path) -> "FontMetrics":
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise CaptionLayoutReviewRequired("所选字幕字体文件不存在")
        try:
            font = TTFont(str(resolved), lazy=True)
            cmap = font.getBestCmap() or {}
            advances = dict(font["hmtx"].metrics)
            units_per_em = int(font["head"].unitsPerEm)
            font.close()
        except Exception as exc:
            raise CaptionLayoutReviewRequired("无法读取所选字幕字体的真实字宽") from exc
        if not cmap or not advances or units_per_em <= 0:
            raise CaptionLayoutReviewRequired("所选字幕字体缺少可用字宽数据")
        return cls(resolved, units_per_em, cmap, advances)

    def text_width_em(self, text: str) -> float:
        width = 0.0
        missing: list[str] = []
        for character in text:
            glyph = self.cmap.get(ord(character))
            metric = self.advances.get(glyph or "")
            if metric is None:
                missing.append(character)
                continue
            width += float(metric[0]) / self.units_per_em
        if missing:
            preview = "".join(dict.fromkeys(missing))[:8]
            raise CaptionLayoutReviewRequired(
                f"所选字体缺少字幕字符：{preview}"
            )
        return width


def _normalized_caption_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _split_one_line(
    text: str, metrics: FontMetrics, *, maximum_width_em: float
) -> list[str]:
    normalized = _normalized_caption_text(text)
    if not normalized:
        raise CaptionLayoutReviewRequired("字幕内容为空")
    if metrics.text_width_em(normalized) <= maximum_width_em:
        return [normalized]

    chunks: list[str] = []
    cursor = 0
    while cursor < len(normalized):
        end = cursor
        last_break: int | None = None
        while end < len(normalized):
            candidate = normalized[cursor : end + 1]
            if metrics.text_width_em(candidate) > maximum_width_em:
                break
            if normalized[end] in _BREAK_CHARS:
                last_break = end + 1
            end += 1
        if end == cursor:
            raise CaptionLayoutReviewRequired("单个字幕字符超过画面安全宽度")
        cut = last_break if last_break and last_break > cursor else end
        chunk = normalized[cursor:cut].strip()
        if not chunk:
            raise CaptionLayoutReviewRequired("字幕无法可靠拆成单行")
        chunks.append(chunk)
        cursor = cut
        while cursor < len(normalized) and normalized[cursor].isspace():
            cursor += 1
    return chunks


def _allocate_cue_chunks(
    cue: CaptionCue,
    chunks: list[str],
    metrics: FontMetrics,
) -> list[CaptionCue]:
    if len(chunks) == 1:
        return [CaptionCue(cue.start_us, cue.duration_us, chunks[0])]
    if cue.duration_us < len(chunks) * CAPTION_MIN_SLICE_US:
        raise CaptionLayoutReviewRequired("字幕时间过短，无法安全拆成多条单行字幕")
    weights = [max(metrics.text_width_em(chunk), 0.01) for chunk in chunks]
    total = sum(weights)
    result: list[CaptionCue] = []
    cursor = cue.start_us
    allocated = 0
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        if index == len(chunks) - 1:
            duration = cue.end_us - cursor
        else:
            next_allocated = round(cue.duration_us * sum(weights[: index + 1]) / total)
            duration = next_allocated - allocated
            allocated = next_allocated
        if duration < CAPTION_MIN_SLICE_US:
            raise CaptionLayoutReviewRequired("字幕拆分后的显示时间过短")
        result.append(CaptionCue(cursor, duration, chunk))
        cursor += duration
    return result


def layout_one_line_captions(
    raw_cues: Iterable[object],
    *,
    font_path: str | Path,
    font_size: float = CAPTION_REFERENCE_FONT_SIZE,
    max_width_ratio: float = CAPTION_MAX_WIDTH_RATIO,
) -> list[dict[str, int | str]]:
    """Derive one-line render cues while preserving every provider cue range."""

    safe_size = float(font_size)
    safe_ratio = float(max_width_ratio)
    if safe_size <= 0:
        raise CaptionLayoutReviewRequired("字幕字号必须大于 0")
    if not 0.2 <= safe_ratio <= CAPTION_MAX_WIDTH_RATIO:
        raise CaptionLayoutReviewRequired("字幕宽度必须在画面宽度 20%–80% 之间")
    metrics = FontMetrics.load(font_path)
    maximum_width_em = (
        CAPTION_REFERENCE_MAX_EM
        * (safe_ratio / CAPTION_MAX_WIDTH_RATIO)
        * (CAPTION_REFERENCE_FONT_SIZE / safe_size)
    )
    result: list[CaptionCue] = []
    for cue in caption_cues_from_payload(raw_cues):
        chunks = _split_one_line(
            cue.text,
            metrics,
            maximum_width_em=maximum_width_em,
        )
        result.extend(_allocate_cue_chunks(cue, chunks, metrics))
    if not result:
        raise CaptionLayoutReviewRequired("当前音频没有可用的 MiniMax 字幕时间轴")
    return [cue.as_dict() for cue in result]


def _latest_postprocess_operations(
    project: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for operation in project.get("operations", []):
        if (
            operation.get("operation_type")
            in {"POSTPROCESS_GENERATE", "POSTPROCESS_EXPORT"}
            and operation.get("item_id")
        ):
            latest[str(operation["item_id"])] = operation
    return latest


class ProjectPostprocessCoordinator:
    """Build browser preview recipes and export them only on explicit request."""

    def __init__(
        self,
        store: ProjectStore,
        render_queue: Any,
        *,
        storage_root: Path,
        draft_root: Path,
        fonts: list[dict[str, Any]],
        bgm_assets: list[dict[str, Any]],
    ) -> None:
        self.store = store
        self.render_queue = render_queue
        self.storage_root = Path(storage_root).resolve()
        self.draft_root = Path(draft_root).resolve()
        self.fonts = {
            str(item.get("identity") or ""): item
            for item in fonts
            if item.get("identity") and item.get("available") and item.get("path")
        }
        self.bgm_assets = {
            str(item.get("identity") or ""): item
            for item in bgm_assets
            if item.get("identity") and item.get("available", True)
        }

    def start(
        self,
        owner_user_id: str,
        project_id: str,
        *,
        idempotency_key: str,
        item_settings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        project = self.store.get_project(owner_user_id, project_id)
        clean_key = str(idempotency_key or "").strip()
        if not clean_key:
            raise ValueError("字幕与背景音乐预览请求缺少幂等键")
        repeated_operations = [
            operation
            for operation in project.get("operations", [])
            if operation.get("operation_type") == "POSTPROCESS_GENERATE"
            and operation.get("idempotency_key") == clean_key
        ]
        if repeated_operations and all(
            operation.get("status") == "SUCCEEDED"
            or operation.get("result", {}).get("job_id")
            for operation in repeated_operations
        ):
            return self.sync(owner_user_id, project_id)
        if any(item["status"] == "POSTPROCESS_RUNNING" for item in project["items"]):
            raise ValueError("当前视频正在按需导出，请勿重复提交")
        if not (
            project["allowed_actions"].get("start_postprocess")
            or project["allowed_actions"].get("retry_postprocess")
        ):
            raise ValueError("当前项目尚未准备好生成字幕与 BGM 成片")
        supplied = {
            str(item.get("item_id") or ""): item
            for item in item_settings
            if isinstance(item, dict) and item.get("item_id")
        }
        subtitle_updates: list[tuple[dict[str, Any], dict[str, Any]]] = []

        target_items = [
            item
            for item in project["items"]
            if item.get("outputs", {}).get("composition_video") is None
        ]
        if not target_items:
            raise ValueError("当前项目没有需要生成的完整预览")

        for item in target_items:
            config = supplied.get(str(item["item_id"]), {})
            base_video = item.get("outputs", {}).get("base_video")
            if not isinstance(base_video, dict) or not base_video.get("managed_path"):
                raise ValueError(f"任务 {item['row_key']} 缺少基础视频")
            font_identity = str(config.get("font_identity") or "").strip()
            font = self.fonts.get(font_identity)
            if font is None:
                raise ValueError(f"任务 {item['row_key']} 选择的字幕字体不可用")
            bgm_identity = str(config.get("bgm_identity") or "").strip()
            if bgm_identity and bgm_identity not in self.bgm_assets:
                raise ValueError(f"任务 {item['row_key']} 选择的 BGM 不可用")
            color = str(config.get("text_color") or "#FFFFFF").strip().upper()
            if _HEX_COLOR.fullmatch(color) is None:
                raise ValueError(f"任务 {item['row_key']} 的字幕颜色不合法")
            raw_cues = item.get("subtitles", {}).get("raw_cues", [])
            try:
                render_cues = layout_one_line_captions(
                    raw_cues,
                    font_path=str(font["path"]),
                    font_size=CAPTION_REFERENCE_FONT_SIZE,
                    max_width_ratio=CAPTION_MAX_WIDTH_RATIO,
                )
            except CaptionLayoutReviewRequired as exc:
                subtitles = dict(item.get("subtitles") or {})
                subtitles.update(
                    {
                        "render_cues": [],
                        "status": "REVIEW_REQUIRED",
                        "overflow_risk": True,
                        "review_reason": str(exc),
                    }
                )
                self.store.set_item_subtitles(
                    owner_user_id, project_id, item["item_id"], subtitles
                )
                raise ValueError(f"任务 {item['row_key']} 字幕需要人工检查：{exc}") from exc

            subtitles = dict(item.get("subtitles") or {})
            subtitles.update(
                {
                    "render_cues": render_cues,
                    "status": "PREVIEW_READY",
                    "overflow_risk": False,
                    "review_reason": None,
                    "bound_video_asset_id": base_video.get("asset_id"),
                    "style": {
                        "font_id": font_identity,
                        "font_name": str(font.get("name") or ""),
                        "font_size": CAPTION_REFERENCE_FONT_SIZE,
                        "text_color": color,
                        "max_width_ratio": CAPTION_MAX_WIDTH_RATIO,
                        "max_lines": CAPTION_MAX_LINES,
                        "bottom_offset_ratio": CAPTION_BOTTOM_OFFSET_RATIO,
                        "transform_y": CAPTION_TRANSFORM_Y,
                    },
                }
            )
            subtitle_updates.append((item, subtitles))
        for item, subtitles in subtitle_updates:
            selected = supplied.get(str(item["item_id"]), {})
            self.store.configure_item_postprocess(
                owner_user_id,
                project_id,
                item["item_id"],
                font_identity=str(subtitles["style"]["font_id"]),
                bgm_identity=str(selected.get("bgm_identity") or ""),
                text_color=str(subtitles["style"]["text_color"]),
            )
            self.store.set_item_subtitles(
                owner_user_id, project_id, item["item_id"], subtitles
            )
            operation = self.store.create_operation(
                owner_user_id=owner_user_id,
                project_id=project_id,
                item_id=item["item_id"],
                operation_type="POSTPROCESS_GENERATE",
                idempotency_key=clean_key,
                payload={
                    "base_video_asset_id": item.get("outputs", {})
                    .get("base_video", {})
                    .get("asset_id"),
                    "font_identity": subtitles["style"]["font_id"],
                    "bgm_identity": selected.get("bgm_identity") or None,
                    "caption_max_width_ratio": CAPTION_MAX_WIDTH_RATIO,
                    "caption_max_lines": CAPTION_MAX_LINES,
                    "caption_bottom_offset_ratio": CAPTION_BOTTOM_OFFSET_RATIO,
                },
            )
            self.store.transition_operation(
                owner_user_id,
                project_id,
                item["item_id"],
                operation_type="POSTPROCESS_GENERATE",
                status="SUCCEEDED",
                item_status="COMPOSITION_READY",
                result={
                    "operation_id": operation["operation_id"],
                    "preview_mode": "browser",
                    "base_video_asset_id": item.get("outputs", {})
                    .get("base_video", {})
                    .get("asset_id"),
                    "caption_cue_count": len(subtitles["render_cues"]),
                    "bgm_identity": selected.get("bgm_identity") or None,
                },
            )
        return self.store.get_project(owner_user_id, project_id)

    def export_preview(
        self,
        owner_user_id: str,
        project_id: str,
        item_id: str,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Export one browser preview only when the user explicitly requests a file."""

        project = self.store.get_project(owner_user_id, project_id)
        clean_key = str(idempotency_key or "").strip()
        if not clean_key:
            raise ValueError("按需导出请求缺少幂等键")
        item = next(
            (entry for entry in project["items"] if str(entry["item_id"]) == str(item_id)),
            None,
        )
        if item is None:
            raise KeyError("脚本行不存在")
        if item.get("outputs", {}).get("composition_video") is not None:
            return project
        if item.get("status") == "POSTPROCESS_RUNNING":
            return self.sync(owner_user_id, project_id)
        subtitles = dict(item.get("subtitles") or {})
        if subtitles.get("status") != "PREVIEW_READY" or not subtitles.get("render_cues"):
            raise ValueError("请先生成浏览器字幕与 BGM 预览")
        repeated = [
            operation
            for operation in project.get("operations", [])
            if operation.get("operation_type") == "POSTPROCESS_EXPORT"
            and operation.get("item_id") == item["item_id"]
            and operation.get("idempotency_key") == clean_key
        ]
        if repeated and any(operation.get("result", {}).get("job_id") for operation in repeated):
            return self.sync(owner_user_id, project_id)
        base_video = item.get("outputs", {}).get("base_video")
        if not isinstance(base_video, dict) or not base_video.get("managed_path"):
            raise ValueError("当前浏览器预览缺少画面源文件")
        style = dict(subtitles.get("style") or {})
        settings = dict(item.get("settings", {}).get("postprocess") or {})
        font_identity = str(style.get("font_id") or settings.get("font_identity") or "")
        font = self.fonts.get(font_identity)
        if font is None:
            raise ValueError("浏览器预览绑定的字幕字体不可用")
        bgm_identity = str(settings.get("bgm_identity") or "")
        if bgm_identity and bgm_identity not in self.bgm_assets:
            raise ValueError("浏览器预览绑定的 BGM 不可用")
        output = (
            self.storage_root
            / "projects"
            / str(owner_user_id)
            / project_id
            / str(item["item_id"])
            / "composition"
            / f"composition-{uuid.uuid4().hex}.mp4"
        )
        job = {
            "schema": "jyd.render_job.v1",
            "source": {
                "type": "video",
                "media_path": str(Path(str(base_video["managed_path"])).resolve()),
            },
            "output": {
                "draft_root": str(self.draft_root),
                "mp4_path": str(output),
                "skip_export": False,
            },
            "captions": {
                "cues": subtitles["render_cues"],
                "track_name": "MiniMax 单行字幕",
                "size": float(style.get("font_size") or CAPTION_REFERENCE_FONT_SIZE),
                "color": str(style.get("text_color") or "#FFFFFF"),
                "transform_x": 0.0,
                "transform_y": CAPTION_TRANSFORM_Y,
                "line_max_width": CAPTION_MAX_WIDTH_RATIO,
                "max_lines": 1,
                "single_line": True,
                "font_id": str(font.get("resource_id") or ""),
                "font_path": str(font["path"]),
                "font_title": str(font.get("name") or ""),
            },
            "audios": (
                [
                    {
                        "type": "bgm",
                        "library_identity": bgm_identity,
                        "target_start_us": 0,
                        "target_duration_us": 0,
                        "fit_to_video": True,
                        "volume": 0.3,
                    }
                ]
                if bgm_identity
                else []
            ),
            "export": {"resolution": "1080P", "framerate": "30fps"},
        }
        operation = self.store.create_operation(
            owner_user_id=owner_user_id,
            project_id=project_id,
            item_id=item["item_id"],
            operation_type="POSTPROCESS_EXPORT",
            idempotency_key=clean_key,
            payload={"reason": "explicit_download", "base_video_asset_id": base_video.get("asset_id")},
        )
        try:
            submitted = self.render_queue.submit_batch(
                [job],
                [{"project_id": project_id, "item_id": item["item_id"], "kind": "preview_export"}],
            )
            batch_id = str(submitted.get("batch_id") or "")
            job_ids = [str(value) for value in submitted.get("job_ids", [])]
            if not batch_id or len(job_ids) != 1:
                raise ValueError("剪映任务队列返回了无效的按需导出结果")
            job_id = job_ids[0]
            self.store.add_link(
                owner_user_id=owner_user_id,
                project_id=project_id,
                item_id=item["item_id"],
                system="jianying",
                relation="postprocess_export_job",
                external_id=job_id,
                metadata={"batch_id": batch_id, "reason": "explicit_download"},
            )
            self.store.transition_operation(
                owner_user_id,
                project_id,
                item["item_id"],
                operation_type="POSTPROCESS_EXPORT",
                status="RUNNING",
                item_status="POSTPROCESS_RUNNING",
                result={
                    "batch_id": batch_id,
                    "job_id": job_id,
                    "operation_id": operation["operation_id"],
                },
            )
        except Exception as exc:
            self.store.transition_operation(
                owner_user_id,
                project_id,
                item["item_id"],
                operation_type="POSTPROCESS_EXPORT",
                status="FAILED",
                item_status="COMPOSITION_FAILED",
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
            raise
        return self.sync(owner_user_id, project_id)

    def sync(self, owner_user_id: str, project_id: str) -> dict[str, Any]:
        project = self.store.get_project(owner_user_id, project_id)
        operations = _latest_postprocess_operations(project)
        for item in project["items"]:
            operation = operations.get(str(item["item_id"]))
            if operation is None or operation.get("status") not in {"PENDING", "RUNNING"}:
                continue
            result = operation.get("result") if isinstance(operation.get("result"), dict) else {}
            operation_type = str(operation.get("operation_type") or "POSTPROCESS_GENERATE")
            job_id = str(result.get("job_id") or "")
            if not job_id:
                continue
            try:
                status = self.render_queue.get_status(job_id)
            except Exception as exc:
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item["item_id"],
                    operation_type=operation_type,
                    status="FAILED",
                    item_status="COMPOSITION_FAILED",
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )
                continue
            remote_status = str(status.get("status") or "")
            if remote_status in {"pending", "running"}:
                continue
            if remote_status != "completed":
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item["item_id"],
                    operation_type=operation_type,
                    status="FAILED",
                    item_status="COMPOSITION_FAILED",
                    result={"job_id": job_id},
                    error_code="JY_RENDER_FAILED",
                    error_message=str(status.get("error") or "剪映后处理失败"),
                )
                continue
            render_result = status.get("result") if isinstance(status.get("result"), dict) else {}
            output = Path(str(render_result.get("output_mp4") or "")).resolve()
            if not output.is_file():
                self.store.transition_operation(
                    owner_user_id,
                    project_id,
                    item["item_id"],
                    operation_type=operation_type,
                    status="FAILED",
                    item_status="COMPOSITION_FAILED",
                    result={"job_id": job_id},
                    error_code="OUTPUT_MISSING",
                    error_message="剪映任务完成但成片文件不存在",
                )
                continue
            current = item.get("outputs", {}).get("composition_video")
            subtitles = dict(item.get("subtitles") or {})
            subtitles["status"] = "RENDERED"
            subtitles["overflow_risk"] = False
            self.store.set_item_subtitles(
                owner_user_id, project_id, item["item_id"], subtitles
            )
            if not (
                isinstance(current, dict)
                and current.get("external_ref", {}).get("render_job_id") == job_id
            ):
                self.store.add_asset(
                    owner_user_id=owner_user_id,
                    project_id=project_id,
                    item_id=item["item_id"],
                    asset_type="composition_video",
                    source_type="jianying_postprocess",
                    status="READY",
                    filename=f"{item['row_key']}-composition.mp4",
                    managed_path=str(output),
                    external_ref={"render_job_id": job_id},
                    metadata={
                        "base_video_asset_id": item.get("outputs", {})
                        .get("base_video", {})
                        .get("asset_id"),
                        "captions": "minimax_one_line",
                        "bgm_volume": 0.3,
                    },
                    make_current=True,
                )
            self.store.transition_operation(
                owner_user_id,
                project_id,
                item["item_id"],
                operation_type=operation_type,
                status="SUCCEEDED",
                item_status="COMPOSITION_READY",
                result={
                    "batch_id": result.get("batch_id"),
                    "job_id": job_id,
                    "output_mp4": str(output),
                },
            )
        return self.store.get_project(owner_user_id, project_id)
