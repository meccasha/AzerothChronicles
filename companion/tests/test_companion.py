import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import azchron_companion as c  # noqa: E402


@pytest.fixture(autouse=True)
def tmp_config(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "CONFIG_PATH", tmp_path / "cfg.json")


def make_wtf(tmp_path: Path) -> Path:
    sv = tmp_path / "_retail_" / "WTF" / "Account" / "MYACCOUNT" / "SavedVariables" / c.SV_NAME
    sv.parent.mkdir(parents=True)
    sv.write_text('AzerothChroniclesDB = { ["records"] = {} }\n')
    return sv


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_find_and_upload_only_when_changed(tmp_path):
    sv = make_wtf(tmp_path)
    assert c.find_savedvariables([tmp_path / "_retail_"]) == [sv]
    calls = []

    def opener(req, timeout):
        calls.append((req.full_url, req.headers["Authorization"], req.data))
        return FakeResp(json.dumps({"normalized": 1, "duplicates": 0, "rejected": 0}).encode())

    cfg = c.Config(server="https://example.test/", token="act_secret")
    assert c.upload(cfg, sv, opener=opener)["normalized"] == 1
    assert calls[0][0] == "https://example.test/api/ingest/savedvariables"
    assert calls[0][1] == "Bearer act_secret"
    assert c.upload(cfg, sv, opener=opener) is None  # unchanged -> no request
    sv.write_text('AzerothChroniclesDB = { ["records"] = { { ["id"] = "x" } } }\n')
    c.upload(cfg, sv, opener=opener)
    assert len(calls) == 2
    assert c.Config.load().last_success_at is not None


def test_http_errors_are_recorded(tmp_path):
    import urllib.error

    sv = make_wtf(tmp_path)

    def opener(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"detail":"Not signed in"}'))

    cfg = c.Config(server="https://example.test", token="bad")
    with pytest.raises(RuntimeError, match="HTTP 401"):
        c.upload(cfg, sv, opener=opener)
    assert "401" in c.Config.load().last_error
