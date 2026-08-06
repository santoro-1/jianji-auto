from __future__ import annotations

from pathlib import Path
import shutil
import sys
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "apps" / "processor" / "frontend" / "new"
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jyd_probe.web_api import WebApiSettings, create_app  # noqa: E402


class NewFrontendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = (
            PROJECT_ROOT / "runtime" / "test_tmp" / f"new_frontend_{uuid.uuid4().hex}"
        )
        self.settings = WebApiSettings(
            storage_root=self.root / "storage",
            template_library_root=self.root / "templates",
            default_draft_root=self.root / "drafts",
            audio_library_root=self.root / "audio",
            admin_password="admin-pass",
            admin_session_secret="admin-secret",
            auth_authority=False,
            auth_server_url="http://127.0.0.1:8000",
            execution_mode="agent",
        )
        for directory in (
            self.settings.storage_root,
            self.settings.template_library_root,
            self.settings.default_draft_root,
            self.settings.audio_library_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_new_workspace_uses_real_script_and_image_input_apis(self) -> None:
        html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/api/new/script-template"', html)
        self.assertIn("/api/new/script-imports/preview", html)
        self.assertIn("/content-analysis", html)
        self.assertIn("retryRowContentAnalysis", html)
        self.assertIn("contentAnalysisTargetsForRows", html)
        self.assertIn("startContentAnalysisForChangedScripts", html)
        self.assertIn("AI 智能匹配", html)
        self.assertIn("bgm_selection_mode", html)
        self.assertIn("resolvedBgmIdentity", html)
        self.assertIn(
            "=== 'NOT_REQUESTED'",
            html,
        )
        self.assertIn(
            "startContentAnalysisForChangedScripts(activeProject.project_id, targetRows)",
            html,
        )
        self.assertNotIn("正在逐行分析音乐意图和字幕语义", html)
        self.assertNotIn(
            "void analyzeProjectContent(project.project_id).then(syncProjectInputs)",
            html,
        )
        self.assertIn("/image-mapping", html)
        self.assertIn("uploadProjectImage", html)
        self.assertIn("initializeProjectInputs", html)
        self.assertNotIn("simulateExcelParsing", html)
        self.assertNotIn("loadSampleData", html)
        self.assertNotIn("const sampleImages", html)
        self.assertTrue((FRONTEND_ROOT / "project-script-template.xlsx").is_file())

    def test_workspace_sidebar_collapses_and_table_headers_distinguish_io(self) -> None:
        html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="workspace-grid"', html)
        self.assertIn('id="input-sidebar"', html)
        self.assertIn('id="processing-area"', html)
        self.assertIn('id="input-sidebar-toggle"', html)
        self.assertIn("function toggleInputSidebar()", html)
        self.assertIn("new-workbench-input-sidebar-collapsed", html)
        self.assertIn("input-sidebar-collapsed #processing-area", html)
        self.assertIn('class="table-flow-legend"', html)
        self.assertIn("输入 / 操作", html)
        self.assertIn("生成结果", html)
        self.assertIn("--table-header-accent: #818cf8", html)
        self.assertIn("--table-header-accent: #2dd4bf", html)
        self.assertEqual(html.count('scope="col" class="table-header-input'), 9)
        self.assertEqual(html.count('scope="col" class="table-header-output'), 3)
        self.assertIn(
            'class="table-header-output px-4 py-3.5 w-36">声音预览</th>',
            html,
        )
        self.assertIn(
            'class="table-header-output px-4 py-3.5 w-32 text-center whitespace-nowrap">视频预览</th>',
            html,
        )
        self.assertIn(
            'class="table-header-output px-4 py-3.5 w-32 text-center whitespace-nowrap">变体预览</th>',
            html,
        )

    def test_new_workspace_and_voice_center_use_real_voice_apis(self) -> None:
        workspace = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        voice_center = (FRONTEND_ROOT / "voice-library.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("/api/new/voices", workspace)
        self.assertIn("/audio/generate", workspace)
        self.assertIn("/audio/status", workspace)
        self.assertIn("/items/${rowId}/audio/retry", workspace)
        self.assertIn("/projects/${activeProject.project_id}/voice", workspace)
        self.assertIn("/api/new/voice-creations", voice_center)
        self.assertIn("submitVoiceCreation", voice_center)
        self.assertIn("saveCreatedVoice", voice_center)
        self.assertIn("生成克隆试听", voice_center)
        self.assertIn("保存到音色库", voice_center)
        self.assertIn("activateSavedVoice", voice_center)
        self.assertIn("deleteSavedVoice", voice_center)
        self.assertIn('id="voice-source-preview"', voice_center)
        self.assertIn("使用该音色生成试听语音，是否继续？", voice_center)
        self.assertIn("使用该音色生成试听语音，是否继续？", workspace)
        self.assertNotIn("首次试听将调用 MiniMax", voice_center)
        self.assertNotIn("提取并注入原型库", voice_center)
        self.assertEqual(voice_center.count('id="voice-task-list"'), 1)
        self.assertNotIn("actions.google.com/sounds", workspace)
        self.assertNotIn("actions.google.com/sounds", voice_center)
        self.assertNotIn("startCloningProgress", voice_center)
        self.assertNotIn("addNewVoiceCard", voice_center)
        self.assertNotIn("setInterval", voice_center)
        self.assertNotIn("原型体验", voice_center)
        self.assertNotIn("原型演示", voice_center)
        self.assertNotIn("原型演示", workspace)
        self.assertIn(
            "['wait', 'failed'].includes(row.getAttribute('data-voice-status'))",
            workspace,
        )
        self.assertNotIn(
            "['idle', 'failed'].includes(row.getAttribute('data-voice-status'))",
            workspace,
        )

    def test_complete_video_flow_keeps_internal_stages_out_of_user_results(self) -> None:
        workspace = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("/composition/generate", workspace)
        self.assertIn("/composition/status", workspace)
        self.assertIn("/composition/retry", workspace)
        self.assertIn("data-preview-video-url", workspace)
        self.assertIn("/base-video", workspace)
        self.assertIn("生成完整成片", workspace)
        self.assertIn("/postprocess/generate", workspace)
        self.assertIn("/postprocess-settings", workspace)
        self.assertIn("continueFinalGenerationAfterComposition", workspace)
        self.assertIn("setFinalGenerationPhase('composition')", workspace)
        self.assertIn("startGlobalPostprocess()", workspace)
        self.assertIn("data-final-video-url", workspace)
        self.assertIn("video-preview-time", workspace)
        self.assertIn("loadedmetadata", workspace)
        self.assertIn("updatePreviewCaption", workspace)
        self.assertIn("playPreviewBgm", workspace)
        self.assertIn("previewBgmAudio.volume = 0.3", workspace)
        self.assertIn("/postprocess/export", workspace)
        self.assertIn("下载 MP4 才会按需启动剪映并导出一次", workspace)
        self.assertIn("style.bottom_offset_ratio || 0.2", workspace)
        self.assertIn("const fontSize = 11", workspace)
        self.assertIn("const strokeColor = '#000000'", workspace)
        self.assertNotIn("caption.scrollWidth > caption.clientWidth", workspace)
        self.assertIn("caption.style.whiteSpace = 'nowrap'", workspace)
        self.assertIn("aspect-ratio: 9 / 16", workspace)
        self.assertIn('id="video-preview-play-button"', workspace)
        self.assertIn("button.classList.toggle('opacity-0', isPlaying)", workspace)
        self.assertIn("/original-materials", workspace)
        self.assertIn("/current-video?filename=", workspace)
        self.assertIn("body: file", workspace)
        self.assertNotIn("URL.createObjectURL(file)", workspace)
        self.assertNotIn("00:12 / 00:28", workspace)
        self.assertNotIn("data-base-video-url", workspace)
        self.assertNotIn("下载基础视频", workspace)
        self.assertNotIn("基础视频", workspace)
        self.assertNotIn("生成字幕 + BGM 成片", workspace)
        self.assertNotIn("重试只会重新执行本地剪映后处理", workspace)
        self.assertIn("new FontFace(family, buffer).load()", workspace)
        self.assertIn("fetch(font.preview_url", workspace)
        self.assertIn("applyFontPreviewToElement", workspace)
        self.assertIn("row-subtitle-preview", workspace)
        self.assertIn("字幕预览 · 点击配置", workspace)
        self.assertIn("retryRowPostprocessPreview", workspace)
        self.assertIn("preview-retry-${rowId}", workspace)
        self.assertIn("重新生成字幕/BGM预览", workspace)
        self.assertIn("调整字幕/BGM", workspace)
        self.assertIn("force_retry: true", workspace)
        self.assertIn("const canAdjustPreview = Boolean(activePreviewScript()?.baseVideo)", workspace)
        self.assertNotIn("retryButton.classList.toggle('hidden', !isBrowserCompositionPreview())", workspace)
        self.assertNotIn("将为 ${rows.length} 条视频生成包含字幕和所选背景音乐", workspace)
        self.assertIn("allowed_actions?.retry_postprocess", workspace)
        self.assertIn("重新生成新的声音版本", workspace)
        self.assertIn("pendingRows.length ? pendingRows", workspace)
        self.assertNotIn("4B 使用现有 BGM 素材库", workspace)
        self.assertNotIn("4B 字幕为单行", workspace)
        self.assertNotIn("先生成 4A 基础视频", workspace)
        self.assertNotIn("4A：使用最新图片", workspace)
        self.assertNotIn("4B：单行字幕", workspace)
        self.assertNotIn("images.unsplash.com", workspace)
        self.assertNotIn("selectAlignment", workspace)
        self.assertNotIn("modal-stroke-color", workspace)
        self.assertIn("Boolean(activeProject?.allowed_actions?.generate_variants)", workspace)
        self.assertNotIn("正在重新合成第 ${rowId} 条带 BGM 和字幕的视频", workspace)

    def test_module_6_uses_real_variant_api_and_manual_three_frame_cover(self) -> None:
        workspace = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("/variants/generate", workspace)
        self.assertIn("/variants/status", workspace)
        self.assertIn("/variants/supplement", workspace)
        self.assertIn("/variants/retry", workspace)
        self.assertIn("method: 'DELETE'", workspace)
        self.assertIn("最大差异优先", workspace)
        self.assertIn('id="variant-use-stickers" type="checkbox" checked', workspace)
        self.assertIn("封面固定 3 帧", workspace)
        self.assertIn("frame_count: 3", workspace)
        self.assertIn("frame_time_seconds: 0", workspace)
        self.assertIn("字幕字体和背景音乐继承模块 4B", workspace)
        self.assertIn("D:\\auto\\月.日\\当日批次号", workspace)
        self.assertIn('aspect-[9/16]', workspace)
        self.assertIn("/script-source?filename=", workspace)
        self.assertNotIn("variant-use-subtitles", workspace)
        self.assertNotIn("setTimeout(() => {\n                    markRowVariantsReady", workspace)
        paths = {route.path for route in create_app(self.settings).routes}
        self.assertIn("/api/new/variant-options", paths)
        self.assertIn("/api/new/projects/{project_id}/variant-settings", paths)
        self.assertIn("/api/new/projects/{project_id}/variants/generate", paths)
        self.assertIn("/api/new/projects/{project_id}/variants/status", paths)
        self.assertIn("/api/new/projects/{project_id}/items/{item_id}/variants/supplement", paths)
        self.assertIn("/api/new/projects/{project_id}/items/{item_id}/variants/retry", paths)
        self.assertIn("/api/new/projects/{project_id}/items/{item_id}/variants/{asset_id}", paths)

    def test_module_7_gallery_uses_real_results_and_portrait_preview(self) -> None:
        index = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        gallery = (FRONTEND_ROOT / "gallery.html").read_text(encoding="utf-8")
        self.assertIn("/api/new/gallery", gallery)
        self.assertIn("/api/new/gallery/downloads", gallery)
        self.assertIn("/api/new/gallery/deletions", gallery)
        self.assertIn('id="delete-button"', gallery)
        self.assertIn("删除选中", gallery)
        self.assertIn("deleteSelected", gallery)
        self.assertIn("portrait-frame", gallery)
        self.assertIn("defaultPostprocessFontIdentity", index)
        self.assertIn("[overflow-wrap:anywhere]", index)
        self.assertIn("table-fixed", index)
        self.assertIn("select-all-global", gallery)
        self.assertIn("全选本批次", gallery)
        self.assertIn("batch-modal-grid", gallery)
        self.assertIn("renderBatchOverview", gallery)
        self.assertIn("9 / 16", gallery)
        self.assertIn("filter-project", gallery)
        self.assertIn("filter-date", gallery)
        self.assertIn("filter-batch", gallery)
        self.assertNotIn("images.unsplash.com", gallery)
        self.assertNotIn("Video Card 1", gallery)
        paths = {route.path for route in create_app(self.settings).routes}
        self.assertIn("/api/new/gallery", paths)
        self.assertIn("/api/new/gallery/downloads", paths)
        self.assertIn("/api/new/gallery/deletions", paths)

    def test_new_pages_require_login_but_login_and_logo_are_public(self) -> None:
        with TestClient(create_app(self.settings)) as client:
            for path in ("/app/new", "/app/new/gallery", "/app/new/voices"):
                response = client.get(path, follow_redirects=False)
                self.assertEqual(response.status_code, 303, path)
                self.assertEqual(
                    response.headers["location"],
                    f"/app/new/login?next={path}",
                )

            login = client.get("/app/new/login")
            self.assertEqual(login.status_code, 200)
            self.assertIn("/api/auth/login", login.text)
            self.assertNotIn("demo_vip@shanjian.ai", login.text)
            self.assertNotIn("模拟扫码成功", login.text)

            logo = client.get("/app-static/new/logo.png")
            self.assertEqual(logo.status_code, 200)
            self.assertEqual(logo.headers["content-type"], "image/png")

    def test_digital_account_login_opens_all_new_routes_and_logout_closes_them(self) -> None:
        user = {"user_id": "center-user", "username": "tester", "enabled": True}

        def verify(_client, token):
            return user if token == "center-token" else None

        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "center-token", "user": user},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.verify",
            new=verify,
        ):
            with TestClient(create_app(self.settings)) as client:
                login = client.post(
                    "/api/auth/login",
                    json={
                        "username": "tester",
                        "password": "pass123",
                        "next": "/app/new/gallery",
                    },
                )
                self.assertEqual(login.status_code, 200, login.text)
                self.assertEqual(login.json()["next"], "/app/new/gallery")
                self.assertIn("HttpOnly", login.headers["set-cookie"])

                expected_files = {
                    "/app/new": "index.html",
                    "/app/new/gallery": "gallery.html",
                    "/app/new/voices": "voice-library.html",
                }
                for path, filename in expected_files.items():
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200, path)
                    self.assertEqual(
                        response.text,
                        (FRONTEND_ROOT / filename).read_text(encoding="utf-8"),
                    )
                    self.assertIn("/api/auth/session", response.text)
                    self.assertIn("/api/auth/logout", response.text)
                    self.assertIn("current-user-name", response.text)

                session = client.get("/api/auth/session")
                self.assertTrue(session.json()["authenticated"])
                self.assertEqual(session.json()["username"], "tester")

                logout = client.post("/api/auth/logout")
                self.assertEqual(logout.status_code, 200)
                self.assertIn("Max-Age=0", logout.headers["set-cookie"])
                client.cookies.clear()

                closed = client.get("/app/new", follow_redirects=False)
                self.assertEqual(closed.status_code, 303)
                self.assertEqual(closed.headers["location"], "/app/new/login?next=/app/new")

    def test_logged_in_login_page_only_redirects_inside_new_app(self) -> None:
        user = {"user_id": "center-user", "username": "tester", "enabled": True}

        def verify(_client, token):
            return user if token == "center-token" else None

        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "center-token", "user": user},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.verify",
            new=verify,
        ):
            with TestClient(create_app(self.settings)) as client:
                client.post(
                    "/api/auth/login",
                    json={"username": "tester", "password": "pass123"},
                )
                accepted = client.get(
                    "/app/new/login?next=/app/new/voices", follow_redirects=False
                )
                self.assertEqual(accepted.headers["location"], "/app/new/voices")

                rejected = client.get(
                    "/app/new/login?next=https://example.com", follow_redirects=False
                )
                self.assertEqual(rejected.headers["location"], "/app/new")

    def test_revoked_digital_account_session_cannot_keep_new_page_open(self) -> None:
        user = {"user_id": "center-user", "username": "tester", "enabled": True}
        account_enabled = True

        def verify(_client, token):
            return user if token == "center-token" and account_enabled else None

        with patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "center-token", "user": user},
        ), patch(
            "jyd_probe.auth_center.AuthCenterClient.verify",
            new=verify,
        ):
            with TestClient(create_app(self.settings)) as client:
                client.post(
                    "/api/auth/login",
                    json={"username": "tester", "password": "pass123"},
                )
                self.assertEqual(client.get("/app/new").status_code, 200)

                account_enabled = False
                revoked = client.get("/app/new", follow_redirects=False)
                self.assertEqual(revoked.status_code, 303)
                self.assertEqual(
                    revoked.headers["location"], "/app/new/login?next=/app/new"
                )


if __name__ == "__main__":
    unittest.main()
