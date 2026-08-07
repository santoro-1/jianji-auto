from __future__ import annotations

import shutil
from pathlib import Path
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from jyd_probe.web_api import WebApiSettings, create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_catalog_analysis_review_and_revision_api() -> None:
    root = PROJECT_ROOT / "runtime" / "test_tmp" / f"visual_api_{uuid.uuid4().hex}"
    settings = WebApiSettings(
        storage_root=root / "storage",
        template_library_root=root / "templates",
        default_draft_root=root / "drafts",
        audio_library_root=root / "audio",
        admin_password="admin-pass",
        admin_session_secret="admin-secret",
        auth_authority=False,
        auth_server_url="http://127.0.0.1:8000",
        execution_mode="agent",
    )
    for directory in (
        settings.storage_root,
        settings.template_library_root,
        settings.default_draft_root,
        settings.audio_library_root,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    user = {"user_id": "visual-api-user", "username": "tester", "enabled": True}

    def verify(_client, token):
        return user if token == "center-token" else None

    def analyze(_client, _token, payload, *, force_refresh=False):
        return {
            "schema_version": "jyd.visual-analysis.v1",
            "analysis_status": "SUCCESS",
            "script_sha256": payload["script_sha256"],
            "catalog_version": payload["catalog_version"],
            "decisions": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "decision": "SHOW",
                    "concept_id": candidate["allowed_concepts"][0]["concept_id"],
                    "usage": "literal",
                    "importance": 0.9,
                    "confidence": 0.96,
                    "reason_code": "LITERAL_CONCRETE_OBJECT",
                }
                for candidate in payload["candidates"]
            ],
            "provider_attempts": 1,
            "cache_hit": False,
            "cacheable": True,
            "error": None,
        }

    try:
        with (
            patch(
                "jyd_probe.auth_center.AuthCenterClient.login",
                return_value={"access_token": "center-token", "user": user},
            ),
            patch("jyd_probe.auth_center.AuthCenterClient.verify", new=verify),
            patch(
                "jyd_probe.auth_center.AuthCenterClient.analyze_workbench_visuals",
                new=analyze,
            ),
            TestClient(create_app(settings)) as client,
        ):
            assert client.post(
                "/api/auth/login", json={"username": "tester", "password": "pass123"}
            ).status_code == 200
            catalog_response = client.get("/api/new/semantic-visuals/catalog")
            assert catalog_response.status_code == 200
            catalog = catalog_response.json()
            egg = next(asset for asset in catalog["assets"] if asset["asset_id"] == "egg.boiled.01")
            assert client.get(egg["preview_url"]).headers["content-type"].startswith("image/png")

            project = client.post(
                "/api/new/projects",
                json={
                    "name": "视觉 API",
                    "items": [{"row_key": "1", "script_text": "每天吃一个鸡蛋"}],
                },
            ).json()
            item_id = project["items"][0]["item_id"]
            analyzed = client.post(
                f"/api/new/projects/{project['project_id']}/visual-analysis",
                json={},
            )
            assert analyzed.status_code == 200, analyzed.text
            analysis = analyzed.json()["items"][0]["visual_analysis"]
            assert analysis["analysis_status"] == "SUCCESS"
            assert analysis["mapping_status"] == "FAILED"

            saved = client.put(
                f"/api/new/projects/{project['project_id']}/items/{item_id}/visual-overlays",
                json={
                    "revision": project["revision"],
                    "overlays": [
                        {
                            "overlay_id": "vo-manual-api",
                            "candidate_id": analysis["candidate_request"]["candidates"][0]["candidate_id"],
                            "concept_id": "food.egg",
                            "asset_id": "egg.boiled.01",
                            "enabled": True,
                            "locked": True,
                            "corner": "top_right",
                            "scale": 0.28,
                            "opacity": 1.0,
                            "start_us": 0,
                            "duration_us": 1_800_000,
                        }
                    ],
                },
            )
            assert saved.status_code == 200, saved.text
            frozen = saved.json()["items"][0]["visual_analysis"]["recipe"]["overlays"][0]
            assert frozen["manual"] is True
            assert frozen["selection_mode"] == "manual"
            assert frozen["locked"] is True

            conflict = client.put(
                f"/api/new/projects/{project['project_id']}/items/{item_id}/visual-overlays",
                json={"revision": project["revision"], "overlays": []},
            )
            assert conflict.status_code == 409
    finally:
        shutil.rmtree(root, ignore_errors=True)
