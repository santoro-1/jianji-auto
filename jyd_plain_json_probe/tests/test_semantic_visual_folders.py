from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image
import pytest

import jyd_probe.semantic_visual_folders as folders
from jyd_probe.semantic_visuals import (
    CATALOG_SCHEMA_V3,
    SemanticVisualCatalogError,
    build_visual_recipe,
    frozen_visual_overlays,
    load_semantic_visual_catalog,
    recall_semantic_visual_candidates,
)
from jyd_probe.unified_visual_plan import (
    prepare_unified_visual_input,
    build_local_visual_result,
)


def picture(root, name="食物/鸡蛋/图片/a.png", color="yellow"):
    path = root / folders.SOURCE_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 30), color).save(path)
    return path


def recipe(catalog, *, previous=None, seed="row-1", concept=None):
    cid = concept or next(
        x["concept_id"] for x in catalog.concepts if x["label"] == "鸡蛋"
    )
    return build_visual_recipe(
        catalog=catalog,
        selection_seed=seed,
        previous_recipe=previous,
        mapped_candidates=[
            {
                "candidate_id": "v1",
                "start_us": 0,
                "duration_us": 2_000_000,
                "char_start": 0,
                "char_end": 2,
                "text": "鸡蛋",
                "allowed_concepts": [{"concept_id": cid}],
            }
        ],
        decisions=[
            {
                "candidate_id": "v1",
                "decision": "SHOW",
                "confidence": 1,
                "importance": 1,
                "concept_id": cid,
            }
        ],
    )


@pytest.fixture
def migrated(tmp_path):
    original = tmp_path / "old"
    image = picture(original)
    raw = folders._new_asset(original, image, folders._digest(image), "food.egg")
    raw["asset_id"] = "egg.01"
    raw["rights_status"] = "attributed"
    raw["concept_ids"] = raw["auto_trigger_concept_ids"] = [
        "food.egg",
        "meal.breakfast",
    ]
    raw["semantic_roles"]["depicts"] = list(raw["concept_ids"])
    raw["trigger_basis"] = {cid: "exact_subject" for cid in raw["concept_ids"]}
    video_path = original / "video.mp4"
    video_path.write_bytes(b"reviewed-video-fixture")
    video = {
        **json.loads(json.dumps(raw)),
        "asset_id": "egg.video.01",
        "media_type": "video",
        "renderer": "video_overlay",
        "concept_ids": ["food.egg"],
        "auto_trigger_concept_ids": ["food.egg"],
        "trigger_basis": {"food.egg": "exact_subject"},
        "resource": {
            "video": "video.mp4",
            "preview": raw["resource"]["preview"],
            "duration_us": 12_000_000,
            "width": 120,
            "height": 90,
            "has_audio": True,
        },
        "defaults": {
            "corner": "center",
            "scale": 1,
            "opacity": 1,
            "duration_us": 2_000_000,
            "source_start_us": 4_000_000,
            "mute": True,
            "loop": False,
            "fit": "cover",
        },
        "usage_modes": ["semantic_overlay", "full_screen_broll", "seam_broll"],
    }
    payload = {
        "schema": CATALOG_SCHEMA_V3,
        "library_id": "test",
        "concepts": [
            {
                "concept_id": "food.egg",
                "label": "鸡蛋",
                "description": "食物鸡蛋",
                "aliases": ["鸡蛋", "水煮蛋"],
            },
            {
                "concept_id": "meal.breakfast",
                "label": "早餐",
                "description": "早餐餐食",
                "aliases": ["早餐"],
            },
        ],
        "assets": [raw, video],
    }
    (original / "catalog.json").write_text(json.dumps(payload), encoding="utf-8")
    target = tmp_path / "new"
    result = folders.migrate_catalog(original, target)
    assert result == {"images": 1, "videos": 1, "source_files": 3}
    return original, target, payload


@pytest.mark.parametrize("suffix", ["png", "jpg", "jpeg", "webp", "bmp"])
def test_new_images_and_small_category_only(tmp_path, suffix):
    picture(tmp_path, f"食物/鸡蛋/图片/a.{suffix}")
    catalog = folders.scan_folders(tmp_path)
    assert len(catalog.assets) == 1
    assert recall_semantic_visual_candidates("今天吃鸡蛋", catalog)["candidates"]
    assert not recall_semantic_visual_candidates("今天吃食物", catalog)["candidates"]
    asset = catalog.assets[0]
    assert (Path(asset["bundle_path"]) / "resources/sticker/singleImage.png").is_file()


def test_runtime_never_reads_old_json(tmp_path, monkeypatch):
    picture(tmp_path)
    (tmp_path / "catalog.json").write_text("BROKEN LEGACY JSON", encoding="utf-8")
    monkeypatch.setenv("JYD_SEMANTIC_VISUAL_SOURCE_MODE", "folders")
    assert len(load_semantic_visual_catalog(tmp_path).assets) == 1
    with pytest.raises(SemanticVisualCatalogError):
        load_semantic_visual_catalog(tmp_path, source_mode="json")


def test_no_legacy_fallback_in_empty_folder_mode(tmp_path):
    (tmp_path / "catalog.json").write_text("old unrelated data", encoding="utf-8")
    assert folders.scan_folders(tmp_path).assets == ()


def test_empty_folder_catalog_creates_the_user_drop_directory(tmp_path):
    catalog = folders.FolderCatalog(tmp_path)
    assert catalog.assets == ()
    assert (tmp_path / "素材").is_dir()


def test_scan_unchanged_does_not_hash_media(tmp_path, monkeypatch):
    picture(tmp_path)
    first = folders.scan_folders(tmp_path)
    monkeypatch.setattr(
        folders, "_digest", lambda path: pytest.fail("unchanged media was rehashed")
    )
    second = folders.scan_folders(tmp_path)
    assert second.catalog_version == first.catalog_version


def test_additions_refresh_and_do_not_change_frozen_choice(tmp_path):
    picture(tmp_path)
    live = folders.FolderCatalog(tmp_path)
    first = recipe(live)
    picture(tmp_path, "食物/鸡蛋/图片/b.png", "red")
    updated = live.refresh(force=True)
    assert len(updated.assets) == 2
    second = recipe(updated, previous=first, seed="different")
    assert second["overlays"] == first["overlays"]
    assert second["selection_seed"] == first["selection_seed"]
    assert (
        len(
            {recipe(updated, seed=str(i))["overlays"][0]["asset_id"] for i in range(30)}
        )
        == 2
    )


def test_folder_and_file_rename_keeps_asset_and_concept(tmp_path):
    path = picture(tmp_path)
    first = folders.scan_folders(tmp_path)
    path.rename(path.with_name("renamed.png"))
    folder = path.parent.parent
    folder.rename(folder.with_name("蛋类"))
    second = folders.scan_folders(tmp_path)
    assert first.assets[0]["asset_id"] == second.assets[0]["asset_id"]
    assert first.concepts[0]["concept_id"] == second.concepts[0]["concept_id"]
    assert "蛋类" in second.concepts[0]["aliases"]


def test_deleted_source_stops_new_selection_but_keeps_frozen_render(tmp_path):
    path = picture(tmp_path)
    first = folders.scan_folders(tmp_path)
    frozen = recipe(first)
    path.unlink()
    second = folders.scan_folders(tmp_path)
    assert second.assets[0]["auto_eligible"] is False
    assert not recipe(second)["overlays"]
    remapped = recipe(second, previous=frozen)
    assert remapped["overlays"] == frozen["overlays"]
    overlays = frozen_visual_overlays(
        {"visual_analysis": {"recipe": frozen}}, library_root=tmp_path, catalog=second
    )
    assert len(overlays) == 1
    assert Path(overlays[0]["bundle_path"]).is_dir()


def test_modified_source_does_not_replace_old_media(tmp_path):
    picture(tmp_path)
    first = folders.scan_folders(tmp_path)
    frozen = recipe(first)
    picture(tmp_path, color="blue")
    second = folders.scan_folders(tmp_path)
    assert len(second.assets) == 2
    assert sum(x["auto_eligible"] for x in second.assets) == 1
    assert recipe(second, previous=frozen)["overlays"] == frozen["overlays"]


def test_broken_file_does_not_break_or_replace_good_cache(tmp_path):
    path = picture(tmp_path)
    first = folders.scan_folders(tmp_path)
    path.write_bytes(b"half-written")
    assert folders.scan_folders(tmp_path).catalog_version == first.catalog_version
    path.with_name("new.png").write_bytes(b"invalid")
    assert len(folders.scan_folders(tmp_path).assets) == 1


def test_scan_failure_keeps_last_valid_folder_snapshot(tmp_path, monkeypatch):
    picture(tmp_path)
    live = folders.FolderCatalog(tmp_path)
    previous = live.catalog_version
    monkeypatch.setattr(
        folders,
        "_source_files",
        lambda root: (_ for _ in ()).throw(PermissionError("test")),
    )
    assert live.refresh(force=True).catalog_version == previous


def test_same_bytes_different_categories_not_repeated(tmp_path):
    path = picture(tmp_path)
    other = tmp_path / folders.SOURCE_DIR / "餐食/早餐/图片/copy.png"
    other.parent.mkdir(parents=True)
    shutil.copyfile(path, other)
    catalog = folders.scan_folders(tmp_path)
    assert len(catalog.assets) == 2
    candidates, decisions = [], []
    for i, concept in enumerate(catalog.concepts):
        candidates.append(
            {
                "candidate_id": str(i),
                "start_us": i * 30_000_000,
                "duration_us": 2_000_000,
                "char_start": i * 10,
                "char_end": i * 10 + 2,
                "text": concept["label"],
                "allowed_concepts": [{"concept_id": concept["concept_id"]}],
            }
        )
        decisions.append(
            {
                "candidate_id": str(i),
                "decision": "SHOW",
                "confidence": 1,
                "concept_id": concept["concept_id"],
            }
        )
    result = build_visual_recipe(
        catalog=catalog, mapped_candidates=candidates, decisions=decisions
    )
    assert len(result["overlays"]) == 1


def test_migration_retains_aliases_ranges_permissions_and_originals(migrated):
    original, target, payload = migrated
    catalog = folders.scan_folders(target)
    assert "水煮蛋" in catalog.concept("food.egg")["aliases"]
    video = catalog.asset("egg.video.01")
    assert video["defaults"]["source_start_us"] == 4_000_000
    assert video["defaults"]["duration_us"] == 2_000_000
    assert video["usage_modes"] == payload["assets"][1]["usage_modes"]
    assert video["rights_status"] == "attributed"
    assert (original / "video.mp4").read_bytes() == b"reviewed-video-fixture"
    assert json.loads((original / "catalog.json").read_text()) == payload
    assert folders.migrate_catalog(original, target)["already_imported"]
    assert len(catalog.assets) == 2


def test_removing_one_multiconcept_folder_removes_only_its_binding(migrated):
    _, target, _ = migrated
    path = next((target / folders.SOURCE_DIR / "餐食/早餐/图片").iterdir())
    path.unlink()
    asset = folders.scan_folders(target).asset("egg.01")
    assert asset["concept_ids"] == ["food.egg"]


def test_migration_quarantine_survives_copy_to_new_folder(migrated):
    _, target, _ = migrated
    with folders._connect(target) as connection:
        asset = json.loads(
            connection.execute(
                "SELECT payload FROM assets WHERE id='egg.01'"
            ).fetchone()[0]
        )
        asset["auto_eligible"] = False
        connection.execute(
            "UPDATE assets SET payload=? WHERE id='egg.01'", (json.dumps(asset),)
        )
    source = next((target / folders.SOURCE_DIR / "食物/鸡蛋/图片").iterdir())
    destination = target / folders.SOURCE_DIR / "测试/新类别/图片/new.png"
    destination.parent.mkdir(parents=True)
    shutil.copyfile(source, destination)
    catalog = folders.scan_folders(target)
    assert all(
        not x["auto_eligible"] for x in catalog.assets if x["media_type"] == "image"
    )


def test_new_real_video_is_muted_short_foreground_only(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg unavailable")
    path = tmp_path / folders.SOURCE_DIR / "运动/跑步/视频/test.mp4"
    path.parent.mkdir(parents=True)
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=96x96:d=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    asset = folders.scan_folders(tmp_path).assets[0]
    assert asset["media_type"] == "video"
    assert asset["resource"]["duration_us"] == 1_000_000
    assert asset["defaults"]["mute"] is True
    assert asset["defaults"]["duration_us"] == 1_000_000
    assert asset["usage_modes"] == ["semantic_overlay"]
    assert Path(asset["preview_path"]).is_file()


def test_unified_remapping_keeps_selection_and_row_seed(tmp_path):
    picture(tmp_path)
    catalog = folders.scan_folders(tmp_path)
    item = {
        "item_id": "isolated-row",
        "script_text": "鸡蛋",
        "subtitles": {
            "raw_cues": [{"start_us": 0, "end_us": 2_000_000, "text": "鸡蛋"}]
        },
    }
    visual_input = prepare_unified_visual_input(item, catalog)
    assert visual_input.selection_seed == "isolated-row"
    concept_id = catalog.concepts[0]["concept_id"]
    _, first = build_local_visual_result(
        script="鸡蛋",
        visual_input=visual_input,
        plan=[{"anchor_id": "START", "concept_id": concept_id, "priority": 2}],
        catalog=catalog,
        provider_payload={},
    )
    picture(tmp_path, "食物/鸡蛋/图片/b.png", "red")
    second_catalog = folders.scan_folders(tmp_path)
    item["visual_analysis"] = {"recipe": first}
    _, second = build_local_visual_result(
        script="鸡蛋",
        visual_input=prepare_unified_visual_input(item, second_catalog),
        plan=[{"anchor_id": "START", "concept_id": concept_id, "priority": 2}],
        catalog=second_catalog,
        provider_payload={},
    )
    assert first["overlays"] == second["overlays"]


def test_packaged_images_use_existing_renderer(tmp_path):
    from jyd_probe.render_job import _build_visual_overlay_additions

    picture(tmp_path)
    catalog = folders.scan_folders(tmp_path)
    overlays = frozen_visual_overlays(
        {"visual_analysis": {"recipe": recipe(catalog)}},
        library_root=tmp_path,
        catalog=catalog,
    )
    additions = _build_visual_overlay_additions({"visual_overlays": overlays})
    assert len(additions) == 1
    assert additions[0].image_path.is_file()


def test_failed_index_publication_rolls_back(tmp_path, monkeypatch):
    picture(tmp_path)
    folders.scan_folders(tmp_path)
    picture(tmp_path, "食物/苹果/图片/new.png", "green")
    monkeypatch.setattr(
        folders,
        "_load_snapshot",
        lambda *args: (_ for _ in ()).throw(ValueError("invalid index")),
    )
    with pytest.raises(ValueError, match="invalid index"):
        folders.scan_folders(tmp_path)
    with folders._connect(tmp_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1


def test_migration_retains_broken_source_but_never_selects_it(migrated):
    original, _, payload = migrated
    damaged = original / payload["assets"][0]["resource"]["preview"]
    damaged.write_bytes(damaged.read_bytes()[:90])
    target = original.parent / "with-broken-image"
    result = folders.migrate_catalog(original, target)
    assert result["rejected_assets"] == 1
    catalog = folders.scan_folders(target)
    assert catalog.asset("egg.01") is None
    assert catalog.asset("egg.video.01") is not None
    with folders._connect(target) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM rejected_sources").fetchone()[0]
            == 2
        )
    repaired = next((target / folders.SOURCE_DIR / "食物/鸡蛋/图片").iterdir())
    Image.new("RGB", (40, 30), "blue").save(repaired)
    fixed = [
        asset
        for asset in folders.scan_folders(target).assets
        if asset["media_type"] == "image"
    ]
    assert len(fixed) == 1
    assert fixed[0]["rights_status"] == "attributed"


def test_bad_file_is_retried_only_after_it_changes(tmp_path, monkeypatch):
    path = picture(tmp_path)
    path.write_bytes(b"invalid")
    folders.scan_folders(tmp_path)
    with monkeypatch.context() as context:
        context.setattr(
            folders,
            "_digest",
            lambda path: pytest.fail("unchanged bad file was rehashed"),
        )
        assert not folders.scan_folders(tmp_path).assets
    picture(tmp_path, color="red")
    assert len(folders.scan_folders(tmp_path).assets) == 1


def test_folder_catalog_and_preview_http_endpoints(tmp_path, monkeypatch, migrated):
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    import jyd_probe.web_api as api

    _, root, _ = migrated
    monkeypatch.setattr(api, "SEMANTIC_VISUAL_LIBRARY_ROOT", root)
    monkeypatch.setenv("JYD_SEMANTIC_VISUAL_SOURCE_MODE", "folders")
    settings = api.WebApiSettings(
        storage_root=tmp_path / "store",
        template_library_root=tmp_path / "templates",
        default_draft_root=tmp_path / "drafts",
        audio_library_root=tmp_path / "audio",
        admin_password="local-test",
        admin_session_secret="local-test-secret",
        auth_authority=False,
        auth_server_url="http://127.0.0.1:8000",
        execution_mode="agent",
    )
    for path in (
        settings.storage_root,
        settings.template_library_root,
        settings.default_draft_root,
        settings.audio_library_root,
    ):
        path.mkdir(parents=True, exist_ok=True)
    user = {"user_id": "folder-test", "username": "test", "enabled": True}
    with (
        patch(
            "jyd_probe.auth_center.AuthCenterClient.login",
            return_value={"access_token": "local-token", "user": user},
        ),
        patch("jyd_probe.auth_center.AuthCenterClient.verify", return_value=user),
        patch(
            "jyd_probe.web_api.refresh_saved_visual_plans_for_catalog",
            side_effect=AssertionError(
                "historical projects must not be refreshed at startup"
            ),
        ),
        TestClient(api.create_app(settings)) as client,
    ):
        assert (
            client.post(
                "/api/auth/login", json={"username": "test", "password": "test-pass"}
            ).status_code
            == 200
        )
        response = client.get("/api/new/semantic-visuals/catalog")
        assert response.status_code == 200
        assert response.json()["source_mode"] == "folders"
        assert len(response.json()["assets"]) == 2
        assert (
            client.get("/api/new/semantic-visuals/egg.01/preview")
            .headers["content-type"]
            .startswith("image/")
        )
        video = client.get("/api/new/semantic-visuals/egg.video.01/content")
        assert video.status_code == 200
        assert video.content == b"reviewed-video-fixture"


def test_interrupted_migration_cannot_be_used_as_fresh_library(tmp_path):
    picture(tmp_path)
    with folders._connect(tmp_path) as connection:
        connection.execute(
            "INSERT INTO settings VALUES ('migration_state','in_progress')"
        )
    with pytest.raises(SemanticVisualCatalogError, match="尚未完成"):
        folders.scan_folders(tmp_path)


def test_unchanged_live_library_does_not_rebuild_catalog(tmp_path, monkeypatch):
    picture(tmp_path)
    live = folders.FolderCatalog(tmp_path)
    monkeypatch.setattr(
        folders,
        "_load_snapshot",
        lambda *args: pytest.fail("unchanged catalog was rebuilt"),
    )
    assert live.refresh(force=True).catalog_version == live.catalog_version


def test_test_launcher_has_windows_powershell_encoding_and_isolated_root():
    launcher = Path(__file__).resolve().parents[1] / "start_test_processor.ps1"
    assert launcher.read_bytes().startswith(b"\xef\xbb\xbf")
    source = launcher.read_text(encoding="utf-8-sig")
    assert (
        '$env:JYD_SEMANTIC_VISUAL_LIBRARY_ROOT = Join-Path $Test.Libraries "semantic_visual_library"'
        in source
    )
    assert '[string]$SemanticVisualSource = "folders"' in source
    powershell = shutil.which("powershell.exe")
    if powershell:
        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-Command",
                "$parseErrors=$null; $parseTokens=$null; [System.Management.Automation.Language.Parser]::ParseFile('"
                + launcher.as_posix().replace("'", "''")
                + "',[ref]$parseTokens,[ref]$parseErrors) > $null; if ($parseErrors.Count) { exit 1 }",
            ],
            capture_output=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert result.returncode == 0
