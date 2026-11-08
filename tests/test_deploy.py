from types import SimpleNamespace

import deploy


def fake_port(device="/dev/ttyUSB0", description="CP2102 USB to UART", vid=0x10C4, pid=0xEA60):
    return SimpleNamespace(device=device, description=description, vid=vid, pid=pid)


def test_is_esp_port_recognizes_known_vid():
    assert deploy.is_esp_port(fake_port(vid=0x10C4)) is True
    assert deploy.is_esp_port(fake_port(vid=0x1A86)) is True
    assert deploy.is_esp_port(fake_port(vid=0x303A)) is True
    assert deploy.is_esp_port(fake_port(vid=0x0403)) is True


def test_is_esp_port_rejects_unknown_vid():
    assert deploy.is_esp_port(fake_port(vid=0x1234)) is False


def test_is_esp_port_handles_missing_vid():
    assert deploy.is_esp_port(fake_port(vid=None, pid=None)) is False


def test_format_port_marks_esp():
    assert "ESP: yes" in deploy.format_port(fake_port(vid=0x10C4))
    assert "ESP: no" in deploy.format_port(fake_port(vid=0x1234))
    assert "----:----" in deploy.format_port(fake_port(vid=None, pid=None))


def test_select_port_returns_selected_port():
    ports = [fake_port("/dev/ttyUSB0"), fake_port("/dev/ttyUSB1", vid=0x1234)]
    answers = iter(["2"])
    selected = deploy.select_port(ports, input_fn=lambda _: next(answers), print_fn=lambda *_: None)
    assert selected.device == "/dev/ttyUSB1"


def test_select_port_quits():
    ports = [fake_port()]
    selected = deploy.select_port(ports, input_fn=lambda _: "q", print_fn=lambda *_: None)
    assert selected is None


def test_select_port_reprompts_on_invalid_input():
    ports = [fake_port("/dev/ttyUSB0")]
    answers = iter(["99", "1"])
    selected = deploy.select_port(ports, input_fn=lambda _: next(answers), print_fn=lambda *_: None)
    assert selected.device == "/dev/ttyUSB0"


import io
from pathlib import Path


def test_ensure_firmware_uses_cached_file(tmp_path):
    image = tmp_path / "fw.bin"
    image.write_bytes(b"cached")

    def opener(_url):
        raise AssertionError("should not download when cache exists")

    assert deploy.ensure_firmware(image, opener=opener) == image
    assert image.read_bytes() == b"cached"


def test_ensure_firmware_downloads_when_missing(tmp_path):
    image = tmp_path / "nested" / "fw.bin"

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    assert deploy.ensure_firmware(image, opener=lambda _url: Response(b"downloaded")) == image
    assert image.read_bytes() == b"downloaded"


def test_missing_tools_reports_absent(monkeypatch):
    monkeypatch.setattr(deploy.shutil, "which", lambda name: None)
    assert deploy.missing_tools() == ["esptool", "mpremote"]


def test_upload_firmware_builds_expected_commands(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy, "run", lambda cmd, check=True: calls.append(cmd))
    (tmp_path / "firmware" / "drivers").mkdir(parents=True)

    deploy.upload_firmware("/dev/ttyUSB0", tmp_path)

    flat = " ".join(" ".join(call) for call in calls)
    assert "boot.py" in flat
    assert "config.py" in flat
    assert "main.py" in flat
    assert "wifi_ap.py" in flat
    assert "webserver.py" in flat
    assert ":drivers" in flat
    assert "ina219.py" in flat
    assert "ssd1306.py" in flat


def test_flash_firmware_uses_expected_arguments(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy, "run", lambda cmd, check=True: calls.append(cmd))
    image = tmp_path / "fw.bin"

    deploy.flash_firmware("/dev/ttyUSB0", image)

    assert calls == [[
        "esptool", "--chip", "esp32", "--port", "/dev/ttyUSB0",
        "--baud", "460800", "write_flash", "-z", "0x1000", str(image),
    ]]


def test_main_list_with_no_ports(monkeypatch, capsys):
    monkeypatch.setattr(deploy, "missing_tools", lambda: [])
    monkeypatch.setattr(deploy, "scan_ports", lambda: [])
    assert deploy.main(["--list"]) == 0
    assert "No serial ports detected" in capsys.readouterr().out


def test_main_reports_missing_tools(monkeypatch, capsys):
    monkeypatch.setattr(deploy, "missing_tools", lambda: ["esptool"])
    assert deploy.main([]) == 1
    assert "esptool" in capsys.readouterr().out


def test_main_exits_when_no_ports_and_no_port_flag(monkeypatch, capsys):
    monkeypatch.setattr(deploy, "missing_tools", lambda: [])
    monkeypatch.setattr(deploy, "scan_ports", lambda: [])
    assert deploy.main([]) == 1
    assert "No serial ports detected" in capsys.readouterr().out


def test_main_uses_port_flag_and_runs_steps(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy, "missing_tools", lambda: [])
    monkeypatch.setattr(deploy, "scan_ports", lambda: [])
    monkeypatch.setattr(deploy, "ensure_firmware", lambda path: calls.append("download"))
    monkeypatch.setattr(deploy, "erase_flash", lambda port: calls.append("erase"))
    monkeypatch.setattr(deploy, "flash_firmware", lambda port, image: calls.append("flash"))
    monkeypatch.setattr(deploy, "upload_firmware", lambda port, root: calls.append("upload"))
    monkeypatch.setattr(deploy, "reset_board", lambda port: calls.append("reset"))
    monkeypatch.setattr(deploy, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(deploy.time, "sleep", lambda _seconds: None)

    assert deploy.main(["--port", "/dev/ttyUSB0", "--yes", "--keep-files"]) == 0
    assert calls == ["download", "flash", "upload", "reset"]


def test_scan_ports_filters_legacy_ttyS_ports(monkeypatch):
    class FakeListPorts:
        @staticmethod
        def comports():
            return [
                fake_port("/dev/ttyS0", description="n/a", vid=None, pid=None),
                fake_port("/dev/ttyUSB0"),
            ]

    monkeypatch.setattr(deploy, "list_ports", FakeListPorts)
    assert [port.device for port in deploy.scan_ports()] == ["/dev/ttyUSB0"]
