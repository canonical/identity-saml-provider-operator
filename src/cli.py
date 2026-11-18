# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from ops import Container
from ops.pebble import Error, ExecError

from constants import WORKLOAD_SERVICE
from exceptions import MigrationError, ServiceProviderError

logger = logging.getLogger(__name__)


class CommandLine:
    def __init__(self, container: Container):
        self.container = container

    def get_application_version(self) -> str | None:
        """Get the SAML provider application version."""
        cmd = [
            "/usr/bin/identity-saml-provider",
            "version",
        ]

        try:
            stdout, _ = self._run_cmd(cmd)
        except Error as err:
            logger.error("Failed to fetch the application version: %s", err)
            return None

        return stdout.strip()

    def migrate(self, dsn: str, timeout: float = 120) -> None:
        """Apply the database migration."""
        cmd = [
            "/usr/bin/identity-saml-provider",
            "migrations",
            "apply",
            "--dsn",
            dsn,
        ]

        try:
            self._run_cmd(cmd, service_context=WORKLOAD_SERVICE, timeout=timeout)
        except Error as err:
            logger.error("Failed to migrate the database: %s", err)
            raise MigrationError from err

    def list_service_providers(self, environment: dict[str, str]) -> str:
        """List the registered SAML service providers."""
        cmd = [
            "/usr/bin/identity-saml-provider",
            "service-provider",
            "list",
            "--format",
            "json",
        ]

        try:
            stdout, _ = self._run_cmd(
                cmd, environment=environment, service_context=WORKLOAD_SERVICE
            )
        except ExecError as err:
            # The CLI prints its error envelope ({"status": "error", ...})
            # to stdout before exiting non-zero; surface it instead of a
            # generic exit-code message.
            cli_output = err.stdout.decode() if isinstance(err.stdout, bytes) else err.stdout
            envelope = (cli_output or "").strip()
            message = f"workload CLI exited with code {err.exit_code}"
            if envelope:
                message = f"{message}: {envelope}"
            logger.error("Failed to list service providers: %s", message)
            raise ServiceProviderError(message) from err
        except Error as err:
            logger.error("Failed to list service providers: %s", err)
            raise ServiceProviderError from err

        return stdout

    def _run_cmd(
        self,
        cmd: list[str],
        timeout: float = 20,
        environment: dict[str, str] | None = None,
        service_context: str | None = None,
    ) -> tuple[str, str | None]:
        process = self.container.exec(
            cmd,
            service_context=service_context,
            environment=environment,
            timeout=timeout,
        )

        try:
            stdout, stderr = process.wait_output()
        except ExecError as err:
            logger.error("Exited with code: %d. Error: %s", err.exit_code, err.stderr)
            raise

        return (
            stdout.decode() if isinstance(stdout, bytes) else stdout,
            stderr.decode() if isinstance(stderr, bytes) else stderr,
        )
