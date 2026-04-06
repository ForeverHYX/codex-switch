from typer.testing import CliRunner

from codex_switch.cli import app
from codex_switch.config import save_config
from codex_switch.doctor import DoctorReport, create_doctor_report
from codex_switch.install import install_shim, uninstall_shim
from codex_switch.models import AppConfig, InstanceConfig
from codex_switch.paths import config_path


def test_doctor_report_flags_missing_shim() -> None:
    report = DoctorReport(
        real_codex_found=True,
        shim_precedes_path=False,
        unhealthy_instances=["acct-002"],
    )

    assert report.summary() == "real-codex=ok shim=missing unhealthy=acct-002"


def test_create_doctor_report_recovers_stale_binary_and_reports_health(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    wrapper_bin = tmp_path / "bin"
    real_bin = tmp_path / "real" / "bin"
    wrapper_bin.mkdir(parents=True)
    real_bin.mkdir(parents=True)
    monkeypatch.setenv("PATH", f"{wrapper_bin}:{real_bin}")

    real_codex = real_bin / "codex"
    real_codex.write_text("#!/bin/sh\nprintf 'Requests remaining: 33\\n'\n")
    real_codex.chmod(0o755)

    save_config(
        AppConfig(
            real_codex_path=str(tmp_path / "missing" / "codex"),
            instances=[
                InstanceConfig(
                    name="acct-001",
                    order=1,
                    home_dir=str(tmp_path / "instances" / "acct-001" / "home"),
                )
            ],
        )
    )

    report = create_doctor_report()

    assert report.real_codex_found is True
    assert report.shim_precedes_path is True
    assert report.unhealthy_instances == []


def test_install_and_uninstall_shim(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))

    target = install_shim()
    content = target.read_text()

    assert target == config_path().parent / "bin" / "codex"
    assert target.exists()
    assert target.stat().st_mode & 0o111
    assert "#!/bin/sh" in content
    assert "-m codex_switch.wrapper" in content

    removed = uninstall_shim()

    assert removed == target
    assert not target.exists()


def test_cli_exposes_doctor_and_shim_commands(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_SWITCH_HOME", str(tmp_path))
    target = tmp_path / "bin" / "codex"
    monkeypatch.setattr(
        "codex_switch.cli.create_doctor_report",
        lambda: DoctorReport(real_codex_found=True, shim_precedes_path=False, unhealthy_instances=[]),
    )
    monkeypatch.setattr("codex_switch.cli.install_shim", lambda: target)
    monkeypatch.setattr("codex_switch.cli.uninstall_shim", lambda: target)

    runner = CliRunner()

    doctor_result = runner.invoke(app, ["doctor"])
    install_result = runner.invoke(app, ["install-shim"])
    uninstall_result = runner.invoke(app, ["uninstall"])

    assert doctor_result.exit_code == 0
    assert doctor_result.stdout.strip() == "real-codex=ok shim=missing unhealthy=none"

    assert install_result.exit_code == 0
    assert install_result.stdout.strip() == f"Installed codex shim at {target}"

    assert uninstall_result.exit_code == 0
    assert uninstall_result.stdout.strip() == f"Removed codex shim at {target}"
