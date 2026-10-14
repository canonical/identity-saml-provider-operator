# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import io
import json
import urllib.error
from email.message import Message
from unittest.mock import MagicMock, patch

import pytest
from ops import ModelError
from ops.pebble import CheckStatus

from configs import HydraCertificates
from constants import (
    ADMIN_SERVICE_PROVIDERS_URL,
    ADMIN_SP_ATTRIBUTE_MAPPING_URL,
    APPLICATION_PORT,
    DEFAULT_ACS_BINDING,
    HYDRA_CA_CERT,
    WORKLOAD_ALIVE_CHECK,
    WORKLOAD_READY_CHECK,
    WORKLOAD_SERVICE,
)
from env_vars import DEFAULT_CONTAINER_ENV, EnvVarConvertible
from exceptions import PebbleServiceError, ServiceProviderError
from services import PebbleService, WorkloadService


def _mock_http_response(body: dict[str, object]) -> MagicMock:
    resp = MagicMock()
    resp.__enter__.return_value = resp
    resp.read.return_value = json.dumps(body).encode("utf-8")
    return resp


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

    def test_create_service_provider_when_succeeds(
        self, workload_service: WorkloadService
    ) -> None:
        response_body = {
            "status": "success",
            "message": "Service provider registered",
            "entity_id": "https://sp.example.com",
        }
        with patch(
            "services.urllib.request.urlopen",
            return_value=_mock_http_response(response_body),
        ) as mocked_urlopen:
            result = workload_service.create_service_provider(
                entity_id="https://sp.example.com",
                acs_url="https://sp.example.com/acs",
                attribute_mapping='{"name_id_format": "email"}',
            )

        assert result == {
            "status": "success",
            "message": "Service provider registered",
            "entity-id": "https://sp.example.com",
        }
        req = mocked_urlopen.call_args[0][0]
        assert req.full_url == ADMIN_SERVICE_PROVIDERS_URL
        assert req.get_method() == "POST"
        assert json.loads(req.data.decode("utf-8")) == {
            "entity_id": "https://sp.example.com",
            "acs_url": "https://sp.example.com/acs",
            "acs_binding": DEFAULT_ACS_BINDING,
            "attribute_mapping": {"name_id_format": "email"},
        }

    def test_create_service_provider_when_invalid_attribute_mapping_json(
        self, workload_service: WorkloadService
    ) -> None:
        with pytest.raises(ServiceProviderError, match="Invalid attribute-mapping JSON"):
            workload_service.create_service_provider(
                entity_id="https://sp.example.com",
                acs_url="https://sp.example.com/acs",
                attribute_mapping="{invalid-json",
            )

    def test_create_service_provider_when_attribute_mapping_not_dict(
        self, workload_service: WorkloadService
    ) -> None:
        with pytest.raises(
            ServiceProviderError, match="Invalid attribute-mapping: must be a JSON object"
        ):
            workload_service.create_service_provider(
                entity_id="https://sp.example.com",
                acs_url="https://sp.example.com/acs",
                attribute_mapping='["not", "a", "dict"]',
            )

    def test_update_service_provider_when_no_fields_provided(
        self, workload_service: WorkloadService
    ) -> None:
        with pytest.raises(
            ServiceProviderError,
            match="At least one of acs-url, acs-binding, or attribute-mapping must be provided",
        ):
            workload_service.update_service_provider(entity_id="https://sp.example.com")

    def test_update_service_provider_when_only_attribute_mapping_provided(
        self, workload_service: WorkloadService
    ) -> None:
        response_body = {
            "status": "success",
            "message": "Attribute mapping updated",
        }
        with patch(
            "services.urllib.request.urlopen",
            return_value=_mock_http_response(response_body),
        ) as mocked_urlopen:
            result = workload_service.update_service_provider(
                entity_id="https://sp.example.com",
                attribute_mapping='{"name_id_format": "persistent"}',
            )

        assert result == response_body
        req = mocked_urlopen.call_args[0][0]
        assert req.get_method() == "PUT"
        assert (
            req.full_url
            == f"{ADMIN_SP_ATTRIBUTE_MAPPING_URL}?entity_id=https%3A%2F%2Fsp.example.com"
        )
        assert json.loads(req.data.decode("utf-8")) == {"name_id_format": "persistent"}

    def test_update_service_provider_when_acs_url_merged_with_existing(
        self, workload_service: WorkloadService
    ) -> None:
        existing_sp = {
            "entity_id": "https://sp.example.com",
            "acs_url": "https://sp.example.com/old-acs",
            "acs_binding": DEFAULT_ACS_BINDING,
            "attribute_mapping": {"name_id_format": "email"},
        }
        post_response = {
            "status": "success",
            "message": "Service provider registered",
            "entity_id": "https://sp.example.com",
        }
        with patch(
            "services.urllib.request.urlopen",
            side_effect=[_mock_http_response(existing_sp), _mock_http_response(post_response)],
        ) as mocked_urlopen:
            result = workload_service.update_service_provider(
                entity_id="https://sp.example.com",
                acs_url="https://sp.example.com/new-acs",
            )

        assert result == {
            "status": "success",
            "message": "Service provider registered",
            "entity-id": "https://sp.example.com",
        }
        assert mocked_urlopen.call_count == 2
        get_req = mocked_urlopen.call_args_list[0][0][0]
        assert get_req.get_method() == "GET"
        assert (
            get_req.full_url
            == f"{ADMIN_SERVICE_PROVIDERS_URL}?entity_id=https%3A%2F%2Fsp.example.com"
        )
        post_req = mocked_urlopen.call_args_list[1][0][0]
        assert post_req.get_method() == "POST"
        assert json.loads(post_req.data.decode("utf-8")) == {
            "entity_id": "https://sp.example.com",
            "acs_url": "https://sp.example.com/new-acs",
            "acs_binding": DEFAULT_ACS_BINDING,
            "attribute_mapping": {"name_id_format": "email"},
        }

    def test_update_service_provider_when_existing_record_missing_acs_url(
        self, workload_service: WorkloadService
    ) -> None:
        existing_sp = {
            "entity_id": "https://sp.example.com",
        }
        with (
            patch(
                "services.urllib.request.urlopen",
                return_value=_mock_http_response(existing_sp),
            ),
            pytest.raises(
                ServiceProviderError,
                match="Existing service provider record is missing required acs-url",
            ),
        ):
            workload_service.update_service_provider(
                entity_id="https://sp.example.com",
                acs_binding=DEFAULT_ACS_BINDING,
            )

    def test_get_service_provider_when_succeeds(self, workload_service: WorkloadService) -> None:
        response_body = {
            "entity_id": "https://sp.example.com",
            "acs_url": "https://sp.example.com/acs",
            "acs_binding": DEFAULT_ACS_BINDING,
            "attribute_mapping": {"name_id_format": "email"},
        }
        with patch(
            "services.urllib.request.urlopen",
            return_value=_mock_http_response(response_body),
        ) as mocked_urlopen:
            result = workload_service.get_service_provider(entity_id="https://sp.example.com")

        assert result == {
            "entity-id": "https://sp.example.com",
            "acs-url": "https://sp.example.com/acs",
            "acs-binding": DEFAULT_ACS_BINDING,
            "attribute-mapping": '{"name_id_format": "email"}',
        }
        req = mocked_urlopen.call_args[0][0]
        assert req.get_method() == "GET"
        assert (
            req.full_url == f"{ADMIN_SERVICE_PROVIDERS_URL}?entity_id=https%3A%2F%2Fsp.example.com"
        )

    def test_get_service_provider_without_attribute_mapping(
        self, workload_service: WorkloadService
    ) -> None:
        response_body = {
            "entity_id": "https://sp.example.com",
            "acs_url": "https://sp.example.com/acs",
            "acs_binding": DEFAULT_ACS_BINDING,
        }
        with patch(
            "services.urllib.request.urlopen",
            return_value=_mock_http_response(response_body),
        ):
            result = workload_service.get_service_provider(entity_id="https://sp.example.com")

        assert result == {
            "entity-id": "https://sp.example.com",
            "acs-url": "https://sp.example.com/acs",
            "acs-binding": DEFAULT_ACS_BINDING,
        }

    def test_delete_service_provider_when_succeeds(
        self, workload_service: WorkloadService
    ) -> None:
        response_body = {
            "status": "success",
            "message": "Attribute mapping cleared",
        }
        with patch(
            "services.urllib.request.urlopen",
            return_value=_mock_http_response(response_body),
        ) as mocked_urlopen:
            result = workload_service.delete_service_provider(entity_id="https://sp.example.com")

        assert result == response_body
        req = mocked_urlopen.call_args[0][0]
        assert req.get_method() == "DELETE"
        assert (
            req.full_url
            == f"{ADMIN_SP_ATTRIBUTE_MAPPING_URL}?entity_id=https%3A%2F%2Fsp.example.com"
        )

    def test_send_admin_request_when_http_error_with_json_message(
        self, workload_service: WorkloadService, caplog: pytest.LogCaptureFixture
    ) -> None:
        http_err = urllib.error.HTTPError(
            url=ADMIN_SERVICE_PROVIDERS_URL,
            code=404,
            msg="Not Found",
            hdrs=Message(),
            fp=io.BytesIO(b'{"status": 404, "message": "service_provider not found"}'),
        )
        with (
            patch("services.urllib.request.urlopen", side_effect=http_err),
            caplog.at_level("ERROR"),
            pytest.raises(ServiceProviderError, match="service_provider not found"),
        ):
            workload_service.delete_service_provider(entity_id="https://sp.example.com")

        assert "failed with status 404: service_provider not found" in caplog.text

    def test_send_admin_request_when_http_error_without_json_body(
        self, workload_service: WorkloadService
    ) -> None:
        http_err = urllib.error.HTTPError(
            url=ADMIN_SERVICE_PROVIDERS_URL,
            code=500,
            msg="Internal Server Error",
            hdrs=Message(),
            fp=io.BytesIO(b"plain error text"),
        )
        with (
            patch("services.urllib.request.urlopen", side_effect=http_err),
            pytest.raises(ServiceProviderError, match="Internal Server Error"),
        ):
            workload_service.delete_service_provider(entity_id="https://sp.example.com")

    def test_send_admin_request_when_http_error_with_json_missing_message(
        self, workload_service: WorkloadService
    ) -> None:
        http_err = urllib.error.HTTPError(
            url=ADMIN_SERVICE_PROVIDERS_URL,
            code=500,
            msg="Server Error",
            hdrs=Message(),
            fp=io.BytesIO(b'{"error": "something"}'),
        )
        with (
            patch("services.urllib.request.urlopen", side_effect=http_err),
            pytest.raises(ServiceProviderError, match="Server Error"),
        ):
            workload_service.delete_service_provider(entity_id="https://sp.example.com")

    def test_create_service_provider_without_attribute_mapping(
        self, workload_service: WorkloadService
    ) -> None:
        response_body = {
            "status": "success",
            "message": "Service provider registered",
            "entity_id": "https://sp.example.com",
        }
        with patch(
            "services.urllib.request.urlopen",
            return_value=_mock_http_response(response_body),
        ) as mocked_urlopen:
            workload_service.create_service_provider(
                entity_id="https://sp.example.com",
                acs_url="https://sp.example.com/acs",
            )

        req = mocked_urlopen.call_args[0][0]
        assert json.loads(req.data.decode("utf-8")) == {
            "entity_id": "https://sp.example.com",
            "acs_url": "https://sp.example.com/acs",
            "acs_binding": DEFAULT_ACS_BINDING,
        }

    def test_update_service_provider_when_no_attribute_mapping_in_existing(
        self, workload_service: WorkloadService
    ) -> None:
        existing_sp = {
            "entity_id": "https://sp.example.com",
            "acs_url": "https://sp.example.com/old-acs",
            "acs_binding": DEFAULT_ACS_BINDING,
        }
        post_response = {
            "status": "success",
            "message": "Service provider registered",
            "entity_id": "https://sp.example.com",
        }
        with patch(
            "services.urllib.request.urlopen",
            side_effect=[_mock_http_response(existing_sp), _mock_http_response(post_response)],
        ) as mocked_urlopen:
            workload_service.update_service_provider(
                entity_id="https://sp.example.com",
                acs_url="https://sp.example.com/new-acs",
            )

        post_req = mocked_urlopen.call_args_list[1][0][0]
        assert json.loads(post_req.data.decode("utf-8")) == {
            "entity_id": "https://sp.example.com",
            "acs_url": "https://sp.example.com/new-acs",
            "acs_binding": DEFAULT_ACS_BINDING,
        }

    def test_send_admin_request_when_url_error(
        self, workload_service: WorkloadService, caplog: pytest.LogCaptureFixture
    ) -> None:
        url_err = urllib.error.URLError("Connection refused")
        with (
            patch("services.urllib.request.urlopen", side_effect=url_err),
            caplog.at_level("ERROR"),
            pytest.raises(
                ServiceProviderError,
                match="Failed to communicate with workload admin API",
            ),
        ):
            workload_service.delete_service_provider(entity_id="https://sp.example.com")

        assert "Failed to communicate with Admin API" in caplog.text


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
        mocked_container.get_service.return_value.is_running.return_value = True

        with patch.object(
            new_container_file, "from_workload_container", return_value=new_container_file
        ):
            pebble_service.plan(layer, new_container_file)

        mocked_container.add_layer.assert_called_once_with(WORKLOAD_SERVICE, layer, combine=True)
        mocked_container.push.assert_not_called()
        mocked_container.restart.assert_not_called()
        mocked_container.replan.assert_called_once_with()

    def test_plan_when_service_not_running(
        self,
        mocked_container: MagicMock,
        pebble_service: PebbleService,
        new_container_file: MagicMock,
    ) -> None:
        layer = MagicMock()
        mocked_container.get_service.return_value.is_running.return_value = False

        with patch.object(
            new_container_file, "from_workload_container", return_value=new_container_file
        ):
            pebble_service.plan(layer, new_container_file)

        mocked_container.add_layer.assert_called_once_with(WORKLOAD_SERVICE, layer, combine=True)
        mocked_container.push.assert_not_called()
        mocked_container.restart.assert_called_once_with(WORKLOAD_SERVICE)
        mocked_container.replan.assert_not_called()

    def test_push_files_when_container_file_unchanged(
        self,
        mocked_container: MagicMock,
        pebble_service: PebbleService,
        new_container_file: MagicMock,
    ) -> None:
        with patch.object(
            new_container_file, "from_workload_container", return_value=new_container_file
        ):
            restart_needed = pebble_service.push_files(new_container_file)

        assert restart_needed is False
        mocked_container.push.assert_not_called()

    def test_push_files_when_container_file_changed(
        self,
        mocked_container: MagicMock,
        pebble_service: PebbleService,
        new_container_file: MagicMock,
        existing_container_file: MagicMock,
    ) -> None:
        with patch.object(
            new_container_file, "from_workload_container", return_value=existing_container_file
        ):
            restart_needed = pebble_service.push_files(new_container_file)

        assert restart_needed is True
        mocked_container.push.assert_called_once_with(HYDRA_CA_CERT, "abc", make_dirs=True)

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
