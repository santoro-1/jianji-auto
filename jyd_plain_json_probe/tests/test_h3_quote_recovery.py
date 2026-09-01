from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jyd_probe.h3_quote_recovery import H3QuoteConflict
from jyd_probe.project_h3 import ProjectH3Coordinator
from jyd_probe.project_store import ProjectStore
from test_project_h3 import FakeH3Client


class QuoteClient(FakeH3Client):
    confirms = 0
    prepares = 0
    offline = False

    def prepare_h3_batch(self, token, payload):
        self.prepares += 1
        self.snapshot = {**self.snapshot, "batch_id": f"h3-batch-{self.prepares}",
            "status": "AWAITING_COST_CONFIRMATION",
            "quote_recovery": {"can_cancel_quote": True, "quote_token": "test-quote"},
            "items": [{"item_id": "remote-" + row["row_id"], "row_id": row["row_id"],
                       "status": "AWAITING_COST_CONFIRMATION", "segments": []} for row in payload["rows"]]}
        return copy.deepcopy(self.snapshot)

    def get_h3_batch(self, token, batch_id):
        if self.offline:
            raise OSError("offline")
        return copy.deepcopy(self.snapshot)

    def confirm_h3_batch(self, token, batch_id):
        self.confirms += 1
        self.snapshot["status"] = "ACTIVE"
        return copy.deepcopy(self.snapshot)

    def cancel_h3_quote(self, token, batch_id, **kwargs):
        if self.offline:
            raise OSError("offline")
        assert self.snapshot["status"] == "AWAITING_COST_CONFIRMATION"
        self.snapshot["status"] = "CANCELLED"
        for item in self.snapshot["items"]:
            item["status"] = "CANCELLED"
        return copy.deepcopy(self.snapshot)


@pytest.fixture
def quote(tmp_path):
    store = ProjectStore(tmp_path / "control.db")
    project = store.create_project(owner_user_id="u", owner_username="tester", name="quote",
        items=[{"row_key": "1-1", "script_text": "第一条。"}, {"row_key": "1-2", "script_text": "第二条。"}])
    pid = project["project_id"]
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    store.register_input_image(owner_user_id="u", project_id=pid, filename=image.name,
        content_type="image/png", size_bytes=5, sha256="a" * 64, managed_path=str(image))
    store.apply_image_strategy("u", pid, strategy="loop", reuse_count=1)
    for item in project["items"]:
        for kind, ext in (("audio", "mp3"), ("video", "mp4")):
            path = tmp_path / f"{item['item_id']}.{ext}"
            path.write_bytes(kind.encode())
            if kind == "audio":
                store.add_asset(owner_user_id="u", project_id=pid, item_id=item["item_id"],
                    asset_type="audio", source_type="minimax", status="READY", filename=path.name,
                    managed_path=str(path), make_current=True, metadata={"provider_status": "SUCCESS"},
                    external_ref={"batch_id": "audio", "remote_item_id": item["item_id"], "generation_version": 1})
            else:
                store.add_h3_reference_video(owner_user_id="u", project_id=pid, item_id=item["item_id"],
                    filename=path.name, managed_path=str(path), metadata={})
    client = QuoteClient()
    coordinator = ProjectH3Coordinator(store, client)
    prepared = coordinator.prepare("u", pid, "token", idempotency_key="first", selected_account_ids=[7])
    return coordinator, client, store, pid, [item["item_id"] for item in project["items"]], prepared


def test_resume_with_stable_ids_across_new_coordinator_and_duplicate_clicks(quote):
    coordinator, client, store, pid, ids, _ = quote
    coordinator = ProjectH3Coordinator(store, client)
    checked = coordinator.inspect_quotes("u", pid, "token", item_ids=ids)
    assert checked["batches"][0]["can_resume"]
    coordinator.prepare("u", pid, "token", idempotency_key="new-click", selected_account_ids=[7])
    assert client.prepares == 1 and client.confirms == 0
    coordinator.confirm("u", pid, "token")
    coordinator.confirm("u", pid, "token")
    assert client.confirms == 1


def test_subset_preserves_full_quote_and_never_auto_expands_payment(quote):
    coordinator, client, _, pid, ids, _ = quote
    with pytest.raises(H3QuoteConflict) as error:
        coordinator.prepare("u", pid, "token", idempotency_key="subset", selected_account_ids=[7], item_ids=ids[:1])
    info = error.value.detail["batches"][0]
    assert info["row_ids"] == ["1-1", "1-2"] and not info["same_selection"]
    assert client.confirms == 0 and client.prepares == 1


@pytest.mark.parametrize("change", ["script", "audio_bytes", "video_bytes", "image_bytes", "defaults", "audio_version", "missing", "legacy"])
def test_changed_or_unverifiable_inputs_block_confirmation(quote, change):
    coordinator, client, store, pid, ids, _ = quote
    project = store.get_project("u", pid)
    item = project["items"][0]
    if change in {"audio_bytes", "video_bytes", "image_bytes", "missing"}:
        asset = (item["outputs"]["audio"] if change in {"audio_bytes", "missing"}
                 else item["inputs"]["image" if change == "image_bytes" else "h3_reference_video"])
        path = Path(asset["managed_path"])
        if change == "missing":
            path.rename(path.with_suffix(".saved"))
        else:
            path.write_bytes(b"changed")
    elif change == "defaults":
        store.set_h3_configuration("u", pid, identity_image_ids=[], defaults={"megapixels": 1.2})
    else:
        with store._transaction() as db:
            if change == "script":
                db.execute("UPDATE project_items SET script_text='changed' WHERE item_id=?", (ids[0],))
            elif change == "audio_version":
                audio = item["outputs"]["audio"]
                ref = {**audio["external_ref"], "generation_version": 2}
                db.execute("UPDATE project_assets SET external_ref_json=? WHERE asset_id=?", (json.dumps(ref), audio["asset_id"]))
            else:
                settings = project["settings"]
                settings["h3"]["batches"][0].pop("quote_binding")
                db.execute("UPDATE projects SET settings_json=? WHERE project_id=?", (json.dumps(settings), pid))
    with pytest.raises((H3QuoteConflict, ValueError)):
        coordinator.confirm("u", pid, "token", batch_id="h3-batch-1")
    assert client.confirms == 0


def test_failed_cancel_keeps_link_and_success_releases_both_rows(quote):
    coordinator, client, store, pid, ids, _ = quote
    client.offline = True
    with pytest.raises(OSError):
        coordinator.cancel_quote("u", pid, "token", batch_id="h3-batch-1", request_key="cancel", quote_token="test-quote")
    assert store.get_project("u", pid)["settings"]["h3"]["remote_status"] == "AWAITING_COST_CONFIRMATION"
    with pytest.raises(OSError):
        coordinator.prepare("u", pid, "token", idempotency_key="offline", selected_account_ids=[7])
    client.offline = False
    coordinator.cancel_quote("u", pid, "token", batch_id="h3-batch-1", request_key="cancel", quote_token="test-quote")
    assert all(item["status"] == "AUDIO_READY" for item in store.get_project("u", pid)["items"])
    assert client.prepares == 1 and client.confirms == 0


def test_frontend_runs_real_resume_function_with_ui_rows():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required")
    page = (Path(__file__).resolve().parents[1] / "apps/processor/frontend/new/index.html").read_text(encoding="utf8")
    code = page[page.index("        async function resumeExistingH3Batch(targets)"):page.index("        async function startGlobalH3Generation")]
    harness = r'''
const assert = require('node:assert/strict');
let activeProject={project_id:'p'}, calls=[], confirms=0, mode='resume';
async function workspaceApi(path, options) {
 calls.push(path);
 if(mode==='offline') throw Error('offline');
 if(path.endsWith('/cancel')) return {project:activeProject};
 assert.deepEqual(JSON.parse(options.body).item_ids,['a']);
 return {project:activeProject,h3_batches:[{batch_id:'b'}],batches:[{
 batch_id:'b',status:'AWAITING_COST_CONFIRMATION',can_resume:mode==='resume',
 can_cancel_quote:mode==='cancel',row_ids:['1-1','1-2'],input_matches:true,fee_snapshot:{segment_count:13}}]};
}
function syncProjectInputs(p){activeProject=p;}
async function confirmPreparedH3Batch(){confirms++;}
function showToast(){} function scheduleH3StatusPoll(){}
function h3NeedsLocalMaterialization(){return false;} function h3HasPendingPostprocess(){return false;}
function openConfirmModal(o){assert.match(o.message,/1-1、1-2/);o.onConfirm();}
'''
    checks = r'''
(async()=>{
 assert.equal(await resumeExistingH3Batch([{id:'a',rowKey:'1-1'}]),true);
 assert.equal(confirms,1);
 mode='unsupported';assert.equal(await resumeExistingH3Batch([{id:'a',rowKey:'1-1'}]),true);
 assert.equal(confirms,1);
 mode='cancel';assert.equal(await resumeExistingH3Batch([{id:'a',rowKey:'1-1'}]),false);
 assert.equal(calls.filter(p=>p.endsWith('/cancel')).length,1);assert.equal(confirms,1);
 mode='offline';await assert.rejects(()=>resumeExistingH3Batch([{id:'a',rowKey:'1-1'}]));
 assert.equal(confirms,1);
})().catch(e=>{console.error(e);process.exit(1)});
'''
    subprocess.run([node, "-e", harness + code + checks], check=True, capture_output=True, text=True)


def test_cancel_receipt_survives_delayed_poll_then_only_selected_row_is_reprepared(quote):
    coordinator, client, store, pid, ids, prepared = quote
    coordinator.cancel_quote("u", pid, "token", batch_id="h3-batch-1", request_key="cancel", quote_token="test-quote")
    store.set_h3_batch_snapshot("u", pid, prepare_key="first", snapshot=prepared["h3_batch"])
    assert store.get_project("u", pid)["settings"]["h3"]["remote_status"] == "CANCELLED"
    result = coordinator.prepare("u", pid, "token", idempotency_key="second", selected_account_ids=[7], item_ids=ids[:1])
    assert result["h3_batch"]["batch_id"] == "h3-batch-2"
    assert [item["row_id"] for item in result["h3_batch"]["items"]] == ["1-1"]
    assert result["project"]["items"][1]["status"] == "AUDIO_READY"
    assert client.prepares == 2 and client.confirms == 0


def test_saving_same_settings_keeps_quote_and_unrelated_queries_do_not_block(quote):
    coordinator, client, store, pid, ids, _ = quote
    h3 = store.get_project("u", pid)["settings"]["h3"]
    store.set_h3_configuration("u", pid, identity_image_ids=h3.get("identity_image_ids", []), defaults=h3.get("defaults", {}))
    assert coordinator.inspect_quotes("u", pid, "token", item_ids=ids)["batches"][0]["can_resume"]
    with store._transaction() as db:
        settings = store.get_project("u", pid)["settings"]
        settings["h3"]["batches"].append({"batch_id": "unrelated", "status": "ACTIVE",
            "quote_binding": {"items": [{"item_id": "different-row", "row_id": "other"}]}})
        db.execute("UPDATE projects SET settings_json=? WHERE project_id=?", (json.dumps(settings), pid))
    original = client.get_h3_batch
    def getter(token, batch_id):
        assert batch_id != "unrelated"
        return original(token, batch_id)
    client.get_h3_batch = getter
    assert len(coordinator.inspect_quotes("u", pid, "token", item_ids=ids)["batches"]) == 1
    result = coordinator.confirm("u", pid, "token", batch_id="h3-batch-1")
    assert all(item["status"] == "H3_RUNNING" for item in result["project"]["items"])


def test_diagnostics_include_quote_versions_without_inputs_or_tokens(quote):
    from jyd_probe.project_diagnostics import _safe_project_summary
    _, _, store, pid, _, _ = quote
    summary = _safe_project_summary(store.get_project("u", pid))
    assert summary["runtime"]["quote_recovery_version"] == "jyd.h3-quote-recovery.v1"
    assert len(summary["runtime"]["frontend_sha256"]) == 64
    assert summary["project"]["h3"]["batches"][0]["binding_sha256"]
    content = json.dumps(summary, ensure_ascii=False)
    assert "test-quote" not in content and "第一条。" not in content
    assert "managed_path" not in content


def test_frontend_quote_entry_remains_available_without_media_and_for_soft_chain():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required")
    page = (Path(__file__).resolve().parents[1] / "apps/processor/frontend/new/index.html").read_text(encoding="utf8")
    entry = page[page.index("        function h3HasQuoteForSelection("):page.index("        function latestMinimaxAudio(")]
    activity = page[page.index("        function h3ItemIsActive("):page.index("        function h3StateIsActive(")]
    harness = r'''
const assert=require('node:assert/strict');
const activeProject={};
const H3_ACTIVE_ITEM_STATUSES=new Set(['WAITING_DEPENDENCY','TASK_CREATED','RUNNING']);
function h3BatchRecords(){return [{batch_id:'b',status:'AWAITING_COST_CONFIRMATION',quote_binding:{items:[{item_id:'a'}]}}]}
'''
    checks = r'''
const row={id:'a',rowKey:'renamed',audio:null,image:null,h3ReferenceVideo:null,h3Settings:{remote_status:'AWAITING_COST_CONFIRMATION',segments:[{status:'WAITING_DEPENDENCY'}]}};
assert.equal(h3HasQuoteForSelection([row]),true);
assert.equal(h3HasQuoteForSelection([{id:'other'}]),false);
assert.equal(h3ItemIsActive(row),false);
assert.equal(h3ItemIsActive(row,{includeQuote:true}),true);
row.h3Settings.remote_status='RUNNING';assert.equal(h3ItemIsActive(row),true);
'''
    subprocess.run([node, "-e", harness + entry + activity + checks], check=True, capture_output=True, text=True)
    assert "(h3InputsReady || h3HasQuoteForSelection(h3Targets))" in page
