# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

from unittest.mock import MagicMock, patch

import pytest
from ops import ModelError
from ops.pebble import CheckStatus

from configs import HydraCertificates
from constants import (
    APPLICATION_PORT,
    HYDRA_CA_CERT,
    WORKLOAD_ALIVE_CHECK,
    WORKLOAD_READY_CHECK,
    WORKLOAD_SERVICE,
)
from env_vars import DEFAULT_CONTAINER_ENV, EnvVarConvertible
from exceptions import PebbleServiceError
from services import PebbleService, WorkloadService


class TestWorkloadService:
    @pytest.fixture
    def workload_service(
        self, mocked_container: MagicMock, mocked_unit: MagicMock
    ) -> WorkloadService:
        return WorkloadService(mocked_unit)

    @pytest.mark.parametrize("version, expected", [("v1.0.0", "v1.0.0"), (None, "")])
    def test_get_version(
        self, workload_service: WorkloadService, version: str | None, expected: str
    ) -> None:
        with patch("cli.CommandLine.get_application_version", return_value=version):
            assert workload_service.version == expected

    def test_set_version(self, mocked_unit: MagicMock, workload_service: WorkloadService) -> None:
        workload_service.version = "v1.0.0"
        mocked_unit.set_workload_version.assert_called_once_with("v1.0.0")

    def test_set_empty_version(
        self, mocked_unit: MagicMock, workload_service: WorkloadService
    ) -> None:
        workload_service.version = ""
        mocked_unit.set_workload_version.assert_not_called()

    def test_set_version_with_error(
        self,
        mocked_unit: MagicMock,
        workload_service: WorkloadService,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        error_msg = "Error from unit"
        mocked_unit.set_workload_version.side_effect = Exception(error_msg)

        with caplog.at_level("ERROR"):
            workload_service.version = "v1.0.0"

        mocked_unit.set_workload_version.assert_called_once_with("v1.0.0")
        assert f"Failed to set workload version: {error_msg}" in caplog.text

    def test_is_running(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        mocked_service_info = MagicMock(is_running=MagicMock(return_value=True))
        mocked_container.get_checks.return_value = {
            WORKLOAD_ALIVE_CHECK: MagicMock(status=CheckStatus.UP),
        }

        with patch.object(
            mocked_container, "get_service", return_value=mocked_service_info
        ) as get_service:
            is_running = workload_service.is_running

        assert is_running is True
        get_service.assert_called_once_with(WORKLOAD_SERVICE)
        mocked_container.get_checks.assert_called_once_with(WORKLOAD_ALIVE_CHECK)

    def test_is_running_when_workload_service_not_found(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        with patch.object(mocked_container, "get_service", side_effect=ModelError):
            is_running = workload_service.is_running

        assert is_running is False

    def test_is_running_when_service_not_running(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        mocked_service_info = MagicMock(is_running=MagicMock(return_value=False))

        with patch.object(mocked_container, "get_service", return_value=mocked_service_info):
            assert workload_service.is_running is False
        mocked_container.get_checks.assert_not_called()

    def test_is_running_when_alive_check_down(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        mocked_service_info = MagicMock(is_running=MagicMock(return_value=True))
        mocked_container.get_checks.return_value = {
            WORKLOAD_ALIVE_CHECK: MagicMock(status=CheckStatus.DOWN),
        }

        with patch.object(mocked_container, "get_service", return_value=mocked_service_info):
            assert workload_service.is_running is False

    def test_is_running_when_alive_check_lookup_fails(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        mocked_service_info = MagicMock(is_running=MagicMock(return_value=True))
        mocked_container.get_checks.side_effect = ModelError

        with patch.object(mocked_container, "get_service", return_value=mocked_service_info):
            assert workload_service.is_running is False

    def test_is_running_when_alive_check_missing(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        mocked_service_info = MagicMock(is_running=MagicMock(return_value=True))
        mocked_container.get_checks.return_value = {}

        with patch.object(mocked_container, "get_service", return_value=mocked_service_info):
            assert workload_service.is_running is True

    def test_is_ready_when_all_checks_up(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        mocked_container.get_checks.return_value = {
            WORKLOAD_READY_CHECK: MagicMock(status=CheckStatus.UP),
        }

        assert workload_service.is_ready is True
        mocked_container.get_checks.assert_called_once_with(WORKLOAD_READY_CHECK)

    def test_is_ready_when_any_check_down(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        mocked_container.get_checks.return_value = {
            WORKLOAD_READY_CHECK: MagicMock(status=CheckStatus.DOWN),
        }

        assert workload_service.is_ready is False

    def test_is_ready_when_no_ready_checks_defined(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        mocked_container.get_checks.return_value = {}

        assert workload_service.is_ready is True

    def test_is_ready_when_lookup_fails(
        self, mocked_container: MagicMock, workload_service: WorkloadService
    ) -> None:
        mocked_container.get_checks.side_effect = ModelError

        assert workload_service.is_ready is False

    def test_open_ports(self, mocked_unit: MagicMock, workload_service: WorkloadService) -> None:
        workload_service.open_ports()

        assert mocked_unit.open_port.call_count == 1
        mocked_unit.open_port.assert_any_call(protocol="tcp", port=APPLICATION_PORT)


class TestPebbleService:
    @pytest.fixture
    def pebble_service(self, mocked_unit: MagicMock) -> PebbleService:
        return PebbleService(mocked_unit)

    @pytest.fixture
    def new_container_file(self) -> MagicMock:
        file = MagicMock(spec=HydraCertificates)
        file.file_path = HYDRA_CA_CERT
        file.content = "abc"
        return file

    @pytest.fixture
    def existing_container_file(self) -> MagicMock:
        file = MagicMock(spec=HydraCertificates)
        file.file_path = HYDRA_CA_CERT
        file.content = "def"
        return file

    def test_plan_when_no_container_file_changed(
        self,
        mocked_container: MagicMock,
        pebble_service: PebbleService,
        new_container_file: MagicMock,
    ) -> None:
        layer = MagicMock()

        with patch.object(
            new_container_file, "from_workload_container", return_value=new_container_file
        ):
            pebble_service.plan(layer, new_container_file)

        mocked_container.add_layer.assert_called_once_with(WORKLOAD_SERVICE, layer, combine=True)
        mocked_container.push.assert_not_called()
        mocked_container.restart.assert_not_called()
        mocked_container.replan.assert_called_once_with()

    def test_plan_when_container_file_changed(
        self,
        mocked_container: MagicMock,
        pebble_service: PebbleService,
        new_container_file: MagicMock,
        existing_container_file: MagicMock,
    ) -> None:
        layer = MagicMock()

        with patch.object(
            new_container_file, "from_workload_container", return_value=existing_container_file
        ):
            pebble_service.plan(layer, new_container_file)

        mocked_container.add_layer.assert_called_once_with(WORKLOAD_SERVICE, layer, combine=True)
        mocked_container.push.assert_called_once_with(HYDRA_CA_CERT, "abc", make_dirs=True)
        mocked_container.restart.assert_called_once_with(WORKLOAD_SERVICE)
        mocked_container.replan.assert_not_called()

    def test_plan_raises_error_when_replan_failed(
        self,
        mocked_container: MagicMock,
        pebble_service: PebbleService,
    ) -> None:
        layer = MagicMock()
        mocked_container.replan.side_effect = Exception("error")

        with pytest.raises(
            PebbleServiceError,
            match="Pebble failed to restart the workload service. Error: error",
        ):
            pebble_service.plan(layer)

    def test_plan_raises_error_when_restart_failed(
        self,
        mocked_container: MagicMock,
        pebble_service: PebbleService,
        new_container_file: MagicMock,
        existing_container_file: MagicMock,
    ) -> None:
        layer = MagicMock()
        mocked_container.restart.side_effect = Exception("error")

        with (
            patch.object(
                new_container_file, "from_workload_container", return_value=existing_container_file
            ),
            pytest.raises(
                PebbleServiceError,
                match="Pebble failed to restart the workload service. Error: error",
            ),
        ):
            pebble_service.plan(layer, new_container_file)

    def test_render_pebble_layer_without_extra_env_vars(
        self,
        pebble_service: PebbleService,
    ) -> None:
        layer = pebble_service.render_pebble_layer()

        environment = layer.to_dict()["services"][WORKLOAD_SERVICE]["environment"]
        assert environment == DEFAULT_CONTAINER_ENV

    def test_render_pebble_layer_with_extra_env_vars(
        self,
        pebble_service: PebbleService,
    ) -> None:
        source = MagicMock(spec=EnvVarConvertible)
        another_source = MagicMock(spec=EnvVarConvertible)
        source.to_env_vars.return_value = {"one": "two"}
        another_source.to_env_vars.return_value = {"three": "four"}

        layer = pebble_service.render_pebble_layer(source, another_source)

        environment = layer.to_dict()["services"][WORKLOAD_SERVICE]["environment"]
        assert environment["one"] == "two"
        assert environment["three"] == "four"
        for env_name, env_value in DEFAULT_CONTAINER_ENV.items():
            assert environment[env_name] == env_value
