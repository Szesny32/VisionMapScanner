import os
import subprocess
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "run_ros_tcp_endpoint.sh"


def _launcher_environment(tmp_path, listener, endpoint):
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    setup_file = tmp_path / "setup.bash"
    setup_file.write_text("# mocked ROS setup\n")
    (mock_bin / "ss").write_text(
        "#!/bin/sh\n"
        "if [ \"$MOCK_LISTENER\" = yes ]; then echo 'LISTEN 0 128 127.0.0.1:10000'; fi\n"
    )
    (mock_bin / "pgrep").write_text(
        "#!/bin/sh\n[ \"$MOCK_ENDPOINT\" = yes ]\n"
    )
    (mock_bin / "ros2").write_text(
        "#!/bin/sh\n"
        "echo started > \"$MOCK_STARTED_PATH\"\n"
    )
    for executable in mock_bin.iterdir():
        executable.chmod(0o755)
    environment = os.environ.copy()
    environment.update({
        "PATH": str(mock_bin) + os.pathsep + environment["PATH"],
        "TMPDIR": str(tmp_path),
        "ROS_SETUP_FILE": str(setup_file),
        "MOCK_LISTENER": listener,
        "MOCK_ENDPOINT": endpoint,
        "MOCK_STARTED_PATH": str(tmp_path / "ros2-started"),
    })
    return environment


def test_endpoint_launcher_reuses_existing_ros_tcp_endpoint(tmp_path):
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        env=_launcher_environment(tmp_path, "yes", "yes"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "ROS_TCP_ENDPOINT_REUSED" in result.stdout
    assert not (tmp_path / "ros2-started").exists()


def test_endpoint_launcher_reports_unknown_port_owner_without_start_or_kill(tmp_path):
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        env=_launcher_environment(tmp_path, "yes", "no"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 98
    assert "ROS_TCP_PORT_CONFLICT" in result.stderr
    assert not (tmp_path / "ros2-started").exists()


def test_endpoint_launcher_starts_server_when_port_is_free(tmp_path):
    result = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        env=_launcher_environment(tmp_path, "no", "no"),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert (tmp_path / "ros2-started").exists()
