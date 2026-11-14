import copy
import json
import stat

import pytest
from prepare_installation import ROOT, prepare, validate
from verify_installation import capture, compare, manifest_identity

SHA = "a" * 40


def profile():
    return json.loads((ROOT / "deploy/profiles/example.json").read_text())


def test_bundle_is_private_complete_and_cannot_overwrite_its_database_secret(tmp_path):
    target = tmp_path / "bundle"
    manifest = prepare(profile(), SHA, target)
    env = (target / ".env").read_text()
    password = dict(line.split("=", 1) for line in env.splitlines())["POSTGRES_PASSWORD"]
    assert len(password) == 64
    assert password not in json.dumps(manifest)
    assert stat.S_IMODE(target.stat().st_mode) == 0o700
    assert stat.S_IMODE((target / ".env").stat().st_mode) == 0o600
    assert manifest["revision"] == SHA
    for router in profile()["routers"]:
        for operation in ("install", "remove"):
            content = (target / "routers" / router["id"] / f"{operation}-logging.rsc").read_text()
            assert f':local source "{router["source_ip"]}"' in content
            assert ':local destination "10.77.0.25"' in content
            assert password not in content
    with pytest.raises(FileExistsError):
        prepare(profile(), SHA, target)
    assert (target / ".env").read_text() == env
    other = tmp_path / "other"
    prepare(profile(), SHA, other)
    assert (other / ".env").read_text() != env


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["routers"][0].update(action_name="logs-ai-invalid"),
        lambda p: p["routers"][0].update(action_name='x"; :error "injection'),
        lambda p: p["routers"][0].update(id="../escape"),
        lambda p: p["routers"][0].update(source_ip="8.8.8.8"),
        lambda p: p["routers"][0].update(source_ip="10.77.0.2"),
        lambda p: p["server"].update(health_bind="0.0.0.0"),
        lambda p: p["server"].update(private_ip="127.0.0.1"),
        lambda p: p["server"].update(syslog_port=True),
        lambda p: p["server"].update(core_port=18002),
        lambda p: p.update(POSTGRES_PASSWORD="never-accepted-in-profile"),
        lambda p: p.update(required_event_kinds=["typo.event"]),
    ],
)
def test_invalid_profiles_fail_before_writing_anything(tmp_path, mutate):
    config = profile()
    mutate(config)
    with pytest.raises(ValueError):
        prepare(config, SHA, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()


def test_abbreviated_revision_is_not_a_release(tmp_path):
    with pytest.raises(ValueError):
        prepare(profile(), "aaaaaaa", tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()


def samples(tmp_path):
    manifest = prepare(profile(), SHA, tmp_path / "bundle")
    before = {
        "manifest_sha256": manifest_identity(manifest),
        "revision": SHA,
        "instance_id": "b" * 32,
        "counts": {r["source_ip"]: {} for r in manifest["routers"]},
    }
    after = copy.deepcopy(before)
    for counts in after["counts"].values():
        counts.update(dict.fromkeys(manifest["required_event_kinds"], 1))
    return manifest, before, after


def test_commissioning_requires_new_events_for_each_router_and_kind(tmp_path):
    manifest, before, after = samples(tmp_path)
    assert compare(manifest, before, after)["status"] == "PASS"
    assert compare(manifest, after, after)["status"] == "FAIL"  # Old events prove nothing new.
    after["counts"][manifest["routers"][1]["source_ip"]] = {}
    assert compare(manifest, before, after)["status"] == "FAIL"  # Another router cannot satisfy it.


@pytest.mark.parametrize("failure", ["restart", "revision", "manifest", "negative", "regression"])
def test_commissioning_rejects_unrelated_or_regressed_baselines(tmp_path, failure):
    manifest, before, after = samples(tmp_path)
    if failure == "restart":
        after["instance_id"] = "c" * 32
    elif failure == "revision":
        before["revision"] = "c" * 40
    elif failure == "manifest":
        before["manifest_sha256"] = "c" * 64
    elif failure == "negative":
        before["counts"][manifest["routers"][0]["source_ip"]]["pppoe.authenticated"] = -1
    else:
        before["counts"][manifest["routers"][0]["source_ip"]]["pppoe.authenticated"] = 2
    with pytest.raises(ValueError):
        compare(manifest, before, after)


def test_readiness_rejects_an_old_healthy_revision(tmp_path, monkeypatch):
    manifest, _, _ = samples(tmp_path)
    monkeypatch.setattr("verify_installation.approved_opener", lambda: object())
    monkeypatch.setattr(
        "verify_installation.get_json", lambda *args: ({"status": "ok", "database": "ok"}, "old")
    )
    with pytest.raises(ValueError, match="revision"):
        capture(manifest)


def test_example_profile_is_a_valid_profile():
    assert validate(profile())
