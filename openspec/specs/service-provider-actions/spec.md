# Service Provider Actions Specification

## Purpose

Provides Juju actions (`create-service-provider`, `update-service-provider`,
`get-service-provider`, and `delete-service-provider`) to manage SAML Service
Providers and their custom attribute mappings via the workload's internal Admin
HTTP API.

## Requirements

### Requirement: Create Service Provider Action

The charm SHALL expose a `create-service-provider` Juju action that registers a
SAML Service Provider via `POST /admin/service-providers` on the workload Admin
HTTP API (`http://localhost:8082`).

#### Scenario: Successful creation with required parameters

- **WHEN** the operator runs `create-service-provider` with `entity-id` and
  `acs-url` while the workload container is connected and the workload service
  is running and ready
- **THEN** the charm sends a `POST` request to
  `http://localhost:8082/admin/service-providers` with `entity_id`, `acs_url`,
  and default `acs_binding`
  (`urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST`), and sets the normalized
  response as action results

#### Scenario: Successful creation with custom binding and attribute mapping

- **WHEN** the operator runs `create-service-provider` with `entity-id`,
  `acs-url`, a custom `acs-binding`, and a valid JSON object string for
  `attribute-mapping`
- **THEN** the charm parses `attribute-mapping` into a JSON object, includes
  `attribute_mapping` in the `POST` request payload, and sets the normalized
  response as action results

#### Scenario: Creation fails when attribute-mapping is invalid JSON

- **WHEN** the operator runs `create-service-provider` with an
  `attribute-mapping` value that is not valid JSON or not a JSON object
- **THEN** the charm fails the action with a descriptive error message without
  sending an HTTP request

#### Scenario: Creation fails when workload is not ready

- **WHEN** the operator runs `create-service-provider` while the container is
  disconnected or the workload service is not running or not ready
- **THEN** the charm fails the action indicating that the container or workload
  service is not ready

### Requirement: Update Service Provider Action

The charm SHALL expose an `update-service-provider` Juju action that updates an
existing SAML Service Provider's ACS configuration and/or custom attribute
mapping via the workload Admin HTTP API.

#### Scenario: Updating only attribute-mapping

- **WHEN** the operator runs `update-service-provider` with `entity-id` and
  `attribute-mapping` (without `acs-url` or `acs-binding`)
- **THEN** the charm sends a `PUT` request to
  `http://localhost:8082/admin/service-providers/attribute-mapping` with query
  parameter `entity_id=<entity-id>` and the parsed `attribute-mapping` JSON
  object as payload, and sets the normalized response as action results

#### Scenario: Updating ACS URL or ACS binding

- **WHEN** the operator runs `update-service-provider` with `entity-id` and
  `acs-url` and/or `acs-binding` (with or without `attribute-mapping`)
- **THEN** the charm fetches the existing Service Provider via `GET
  /admin/service-providers?entity_id=<entity-id>`, merges the provided fields
  with the existing Service Provider attributes, sends a `POST` request to
  `http://localhost:8082/admin/service-providers`, and sets the normalized
  response as action results

#### Scenario: Update fails when no update fields are provided

- **WHEN** the operator runs `update-service-provider` with `entity-id` but
  omits all of `acs-url`, `acs-binding`, and `attribute-mapping`
- **THEN** the charm fails the action with an error stating that at least one of
  `acs-url`, `acs-binding`, or `attribute-mapping` must be provided

#### Scenario: Update fails when target Service Provider does not exist

- **WHEN** the operator runs `update-service-provider` for an `entity-id` that
  is not registered in the workload and the Admin HTTP API returns HTTP 404
- **THEN** the charm fails the action with the error message returned by the
  Admin HTTP API

### Requirement: Get Service Provider Action

The charm SHALL expose a `get-service-provider` Juju action that retrieves an
existing SAML Service Provider's configuration via `GET
/admin/service-providers?entity_id=<entity-id>` on the workload Admin HTTP API.

#### Scenario: Successful retrieval of Service Provider

- **WHEN** the operator runs `get-service-provider` with `entity-id` while the
  workload service is running and ready
- **THEN** the charm sends a `GET` request to
  `http://localhost:8082/admin/service-providers` with query parameter
  `entity_id=<entity-id>`, serializes any nested `attribute-mapping` dictionary
  to a JSON string, and sets the normalized response as action results

#### Scenario: Retrieval fails when target Service Provider does not exist

- **WHEN** the operator runs `get-service-provider` for an `entity-id` that is
  not registered in the workload and the Admin HTTP API returns HTTP 404
- **THEN** the charm fails the action with the error message returned by the
  Admin HTTP API

### Requirement: Delete Service Provider Action

The charm SHALL expose a `delete-service-provider` Juju action that clears the
custom attribute mapping rules for a SAML Service Provider via `DELETE
/admin/service-providers/attribute-mapping` on the workload Admin HTTP API.

#### Scenario: Successful deletion of Service Provider attribute mapping

- **WHEN** the operator runs `delete-service-provider` with `entity-id` while
  the workload service is running and ready
- **THEN** the charm sends a `DELETE` request to
  `http://localhost:8082/admin/service-providers/attribute-mapping` with query
  parameter `entity_id=<entity-id>` and sets the normalized response as action
  results

#### Scenario: Deletion fails when Admin HTTP API returns an error

- **WHEN** the operator runs `delete-service-provider` and the Admin HTTP API
  returns an HTTP error status or connection failure
- **THEN** the charm fails the action with a descriptive error message
