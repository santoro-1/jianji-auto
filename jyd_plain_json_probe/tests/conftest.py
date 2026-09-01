"""Shared pytest isolation for source-level business unit tests.

Release builds intentionally enable device authorization as soon as approved
public roots are compiled into :mod:`jyd_probe.device_trust_roots`.  A small
set of older unit-test modules calls protected draft/render internals directly;
those tests verify the underlying business operation rather than its device
boundary.  Keep that distinction explicit instead of adding a runtime bypass
to production code.
"""

from __future__ import annotations

import pytest

from jyd_probe import device_trust_roots


_UNPROTECTED_SOURCE_UNIT_MODULES = frozenset(
    {
        "test_batch_result_center",
        "test_caption_render_contract",
        "test_draft_copy_metadata",
        "test_existing_draft_export",
        "test_h3_video_sequence",
        "test_multi_processor_api",
        "test_project_postprocess",
        "test_ui_automation_thread",
        "test_user_templates",
    }
)


@pytest.fixture(autouse=True)
def isolate_unprotected_source_unit(request, monkeypatch):
    """Disable release enforcement only for explicitly listed business tests."""
    module_name = request.module.__name__.rsplit(".", 1)[-1]
    if module_name in _UNPROTECTED_SOURCE_UNIT_MODULES:
        monkeypatch.setattr(device_trust_roots, "TRUSTED_ISSUERS", ())
