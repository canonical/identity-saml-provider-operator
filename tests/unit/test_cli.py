# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, patch

import pytest
from ops.pebble import Error, ExecError

from cli import CommandLine
from constants import WORKLOAD_SERVICE
from exceptions import MigrationError


class TestCommandLine:
    @pytest.fixture
    def command_line(self, mocked_container: MagicMock) -> CommandLine:
        return CommandLine(mocked_container)

    def test_get_application_version(self, command_line: CommandLine) -> None:
        expected = "v1.0.0"
        cmd_output = "v1.0.0"
        with patch.object(
            command_line,
            "_run_cmd",
            return_value=(cmd_output, ""),
        ) as run_cmd:
            actual = command_line.get_application_version()
            assert actual == expected
            run_cmd.assert_called_with(
                ["/usr/bin/identity-saml-provider", "version"],
            )

    def test_get_application_version_failed(self, command_line: CommandLine) -> None:
        with patch.object(command_line, "_run_cmd", side_effect=Error):
            assert command_line.get_application_version() is None

    def test_migrate(self, command_line: CommandLine) -> None:
        with patch.object(command_line, "_run_cmd") as run_cmd:
            command_line.migrate(dsn="dsn")

        expected_cmd = [
            "/usr/bin/identity-saml-provider",
            "migrate",
            "up",
            "--dsn",
            "dsn",
        ]
        run_cmd.assert_called_once_with(
            expected_cmd, service_context=WORKLOAD_SERVICE, timeout=120
        )

    def test_migrate_failed(self, command_line: CommandLine) -> None:
        with patch.object(command_line, "_run_cmd", side_effect=Error):
            with pytest.raises(MigrationError):
                command_line.migrate(dsn="dsn")

    def test_run_cmd(self, mocked_container: MagicMock, command_line: CommandLine) -> None:
        cmd, expected = ["cmd"], ("stdout", "")

        mocked_process = MagicMock(wait_output=MagicMock(return_value=expected))
        mocked_container.exec.return_value = mocked_process

        actual = command_line._run_cmd(cmd)

        assert actual == expected
        mocked_container.exec.assert_called_once_with(
            cmd,
            service_context=None,
            timeout=20,
            environment=None,
        )

    def test_run_cmd_with_bytes_output(
        self, mocked_container: MagicMock, command_line: CommandLine
    ) -> None:
        cmd = ["cmd"]
        mocked_process = MagicMock(wait_output=MagicMock(return_value=(b"stdout", b"stderr")))
        mocked_container.exec.return_value = mocked_process

        actual = command_line._run_cmd(
            cmd,
            timeout=30,
            environment={"KEY": "VALUE"},
            service_context=WORKLOAD_SERVICE,
        )

        assert actual == ("stdout", "stderr")
        mocked_container.exec.assert_called_once_with(
            cmd,
            service_context=WORKLOAD_SERVICE,
            timeout=30,
            environment={"KEY": "VALUE"},
        )

    def test_run_cmd_failed(self, mocked_container: MagicMock, command_line: CommandLine) -> None:
        cmd = ["cmd"]

        mocked_process = MagicMock(wait_output=MagicMock(side_effect=ExecError(cmd, 1, "", "")))
        mocked_container.exec.return_value = mocked_process

        with pytest.raises(ExecError):
            command_line._run_cmd(cmd)
