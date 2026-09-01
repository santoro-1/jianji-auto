from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jyd_probe import device_agent_transport as transport, render_agent
from jyd_probe.device_agent_journal import AgentJournal
from jyd_probe.device_auth_protocol import DeviceAuthorizationError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(transport, "requires_device_authorization", lambda: False)
    return transport.AgentApiClient("http://127.0.0.1:8010", "central-test-password")


@pytest.mark.parametrize("body", [b"not json secret", b'{"x":1,"x":2}', b'{"x":NaN}', b'[]'])
def test_invalid_response_never_echoes_its_body(client, body):
    client._opener = SimpleNamespace(open=lambda *a, **kw: BytesIO(body))
    with pytest.raises(transport.AgentRequestError) as error:
        client.post("/api/agents/processor-01/claim")
    assert error.value.code == "INVALID_RESPONSE" and "secret" not in str(error.value)


def test_bounded_response(client, monkeypatch):
    monkeypatch.setattr(transport, "MAX_RESPONSE", 64)
    client._opener = SimpleNamespace(open=lambda *a, **kw: BytesIO(b"x" * 65))
    with pytest.raises(transport.AgentRequestError) as error:
        client.post("/api/agents/processor-01/claim")
    assert error.value.code == "RESPONSE_TOO_LARGE"


@pytest.mark.parametrize("failure,code", [
    (HTTPError("http://127.0.0.1", 403, "secret", {}, BytesIO(b'{"code":"DEVICE_PENDING","detail":"secret-token"}')), "DEVICE_PENDING"),
    (URLError("secret-token"), "CONNECTION_UNCERTAIN"),
])
def test_transport_error_does_not_replay_or_disclose_body(client, failure, code):
    calls = []
    def opened(*a, **kw):
        calls.append(1)
        raise failure
    client._opener = SimpleNamespace(open=opened)
    with pytest.raises(transport.AgentRequestError) as error:
        client.post("/api/agents/processor-01/claim")
    assert error.value.code == code and "secret" not in str(error.value) and calls == [1]


def test_real_loopback_redirect_is_never_followed(client):
    paths = []
    class Redirect(BaseHTTPRequestHandler):
        def do_POST(self):
            paths.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/unexpected")
            self.end_headers()
        def do_GET(self):
            paths.append(self.path)
            self.send_response(200)
            self.end_headers()
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    worker.start()
    try:
        client.server_url = f"http://127.0.0.1:{server.server_port}"
        with pytest.raises(transport.AgentRequestError) as error:
            client.post("/api/agents/register", {"agent_id": "processor-01"})
        assert error.value.code == "HTTP_302"
        assert paths == ["/api/agents/register"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_protected_client_cannot_be_constructed_without_authorizer(monkeypatch):
    monkeypatch.setattr(transport, "requires_device_authorization", lambda: True)
    with pytest.raises(DeviceAuthorizationError) as error:
        transport.AgentApiClient("http://127.0.0.1:8010", "common-password")
    assert error.value.code == "DEVICE_AGENT_PROTOCOL_REQUIRED"


@pytest.mark.parametrize("challenge", [
    {}, {"schema": "publicvideo.agent-challenge.v1", "nonce": "x" * 43, "expires_in": True},
    {"schema": "publicvideo.agent-challenge.v1", "nonce": "x" * 43, "expires_in": 121},
    {"schema": "publicvideo.agent-challenge.v1", "nonce": "short", "expires_in": 120},
    {"schema": "wrong", "nonce": "x" * 43, "expires_in": 120},
])
def test_invalid_challenge_never_reaches_signer(client, challenge):
    calls = []
    client.agent_id = "processor-01"
    client.authorizer = SimpleNamespace(headers=lambda *a: pytest.fail("untrusted challenge reached signer"))
    def send(path, payload, extra_headers=None):
        calls.append(path)
        return challenge
    client._send = send
    with pytest.raises(transport.AgentRequestError) as error:
        client.post("/api/agents/processor-01/claim")
    assert error.value.code == "INVALID_CHALLENGE" and calls == [transport.CHALLENGE_PATH]


def test_journal_retains_id_and_refuses_changed_input_or_second_execution(tmp_path):
    journal = AgentJournal(tmp_path)
    claim = {"job_id": "job-1", "payload": {"output": {"skip_export": True}}}
    first = journal.prepare("http://central", "agent-1", 1, claim, claim["payload"])
    again = AgentJournal(tmp_path).prepare("http://central", "agent-1", 1, claim, claim["payload"])
    assert first["execution_id"] == again["execution_id"]
    with pytest.raises(DeviceAuthorizationError):
        journal.prepare("http://central", "agent-1", 1, claim, {"different": True})
    journal.executing(first)
    assert journal.has_unresolved_execution()
    assert journal.pending("http://central", "agent-1", 2) == []
    with pytest.raises(DeviceAuthorizationError):
        journal.executing(first)
    journal.save_result(first, action="complete", payload={"execution_id": first["execution_id"], "result": {"exported": True}})
    assert not journal.has_unresolved_execution()
    assert AgentJournal(tmp_path).pending("http://central", "agent-1", 1)[0]["result"] == first["result"]
    journal.acknowledge(first)
    assert journal.pending("http://central", "agent-1", 1) == []


def test_agent_command_uses_separate_authority_and_verified_account(monkeypatch, tmp_path):
    calls, session = [], SimpleNamespace(user_id=7)
    @contextmanager
    def command(args, *, server_url):
        assert args.device_user == "test-user" and server_url == "https://authority.example"
        calls.append("entered")
        try:
            yield session
        finally:
            calls.append("closed")
    def api(server_url, token, **kwargs):
        assert server_url == "http://127.0.0.1:8010" and token == "central-test"
        assert kwargs["authorizer"].session is session and kwargs["agent_id"] == "processor-01-u7"
        return object()
    class Agent:
        def __init__(self, client, **kwargs):
            assert kwargs["agent_id"] == "processor-01-u7"
        def run_forever(self, *, once):
            assert once is True
            calls.append("ran")
            return 0
    monkeypatch.setattr(render_agent, "command_authorization", command)
    monkeypatch.setattr(render_agent, "AgentApiClient", api)
    monkeypatch.setattr(render_agent, "RenderAgent", Agent)
    monkeypatch.setattr(render_agent, "configure_file_logging", lambda *a: None)
    monkeypatch.setattr(render_agent, "_agent_config_root", lambda: tmp_path)
    result = render_agent.main(["--server-url", "http://127.0.0.1:8010", "--token", "central-test",
                                "--agent-id", "processor-01", "--device-user", "test-user",
                                "--device-auth-server-url", "https://authority.example", "--once"])
    assert result == 0 and calls == ["entered", "ran", "closed"]


def test_agent_command_failure_does_not_print_credentials(monkeypatch, tmp_path, capsys):
    @contextmanager
    def command(*a, **kw):
        raise RuntimeError("secret website password")
        yield
    monkeypatch.setattr(render_agent, "command_authorization", command)
    monkeypatch.setattr(render_agent, "configure_file_logging", lambda *a: None)
    monkeypatch.setattr(render_agent, "_agent_config_root", lambda: tmp_path)
    assert render_agent.main(["--once"]) == 1
    assert "secret" not in capsys.readouterr().err


def test_gui_login_uses_verified_authority_and_does_not_save_website_credentials(monkeypatch, tmp_path):
    import tkinter as tk
    from tkinter import ttk

    variables, buttons, callbacks, calls = [], {}, [], []
    completed = threading.Event()
    session = SimpleNamespace(user_id=7)

    class Variable:
        def __init__(self, value=""):
            self.value = value
            variables.append(self)
        def get(self):
            return self.value
        def set(self, value):
            self.value = value

    class Widget:
        def __init__(self, *args, **kwargs):
            self.command = kwargs.get("command")
            if self.command:
                buttons[kwargs.get("text")] = self.command
        def pack(self, *args, **kwargs): pass
        def grid(self, *args, **kwargs): pass
        def configure(self, *args, **kwargs): pass
        def columnconfigure(self, *args, **kwargs): pass
        def insert(self, *args, **kwargs): pass
        def see(self, *args, **kwargs): pass

    class Root(Widget):
        def title(self, *args): pass
        def geometry(self, *args): pass
        def minsize(self, *args): pass
        def protocol(self, *args): pass
        def after(self, delay, callback):
            callbacks.append(callback)
        def destroy(self): pass
        def mainloop(self):
            variables[-1].set("website-password-test")
            buttons["保存并启动"]()
            assert completed.wait(5), "mock Agent did not finish"
            for worker in threading.enumerate():
                if worker.name == "render-agent-gui":
                    worker.join(timeout=5)
            for callback in callbacks:
                callback()
            assert variables[-1].get() == ""

    for name in ("Frame", "Label", "LabelFrame", "Radiobutton", "Entry", "Button"):
        monkeypatch.setattr(ttk, name, Widget)
    monkeypatch.setattr(tk, "Tk", Root)
    monkeypatch.setattr(tk, "StringVar", Variable)
    monkeypatch.setattr(tk, "Text", Widget)
    monkeypatch.setattr(render_agent, "requires_device_authorization", lambda: True)
    monkeypatch.setattr(render_agent, "_agent_config_root", lambda: tmp_path)
    monkeypatch.setattr(render_agent, "_load_agent_gui_config", lambda: {
        "server_url": "http://127.0.0.1:8010", "token": "central-password-test", "draft_root": str(tmp_path),
        "device_auth_server_url": "https://authority.example", "device_user": "website-user-test",
    })
    def trusted(url):
        assert url == "https://authority.example"
        calls.append("trust")
        return "verified-trust"
    class Accounts:
        def __init__(self, trust):
            assert trust == "verified-trust" and calls == ["trust"]
        def login(self, user, password):
            assert (user, password) == ("website-user-test", "website-password-test")
            calls.append("login")
            return SimpleNamespace(token="website-token-test")
    @contextmanager
    def account_context(account, trust):
        assert account.token == "website-token-test" and trust == "verified-trust"
        calls.append("session")
        try:
            yield session
        finally:
            calls.append("closed")
            completed.set()
    def api(url, token, *, agent_id, authorizer):
        assert token == "central-password-test" and agent_id == "processor-01-u7"
        assert authorizer.session is session
        return object()
    class Agent:
        def __init__(self, client, **kwargs): pass
        def run_forever(self, *, stop_event):
            calls.append("run")
    monkeypatch.setattr(render_agent, "bundled_trust", trusted)
    monkeypatch.setattr(render_agent, "CommandAccountClient", Accounts)
    monkeypatch.setattr(render_agent, "account_authorization", account_context)
    monkeypatch.setattr(render_agent, "AgentApiClient", api)
    monkeypatch.setattr(render_agent, "RenderAgent", Agent)
    assert render_agent.launch_agent_gui() == 0
    saved = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "website-password-test" not in saved and "website-token-test" not in saved
    assert json.loads(saved)["device_user"] == "website-user-test"
    assert calls == ["trust", "login", "session", "run", "closed"]
