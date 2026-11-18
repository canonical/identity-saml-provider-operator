# Spec Delta

## ADDED Requirements

### Requirement: List Service Providers Action

The charm SHALL expose a `list-service-providers` Juju action with no
parameters that returns all registered service providers and their
entity-ids. The action SHALL read the provider list through the workload
CLI command `identity-saml-provider service-provider list --format json`,
executed with the database connection environment. The action SHALL set a
`service-providers` result key that holds the provider list serialized as a
JSON string, because Juju action results require flat string values.

#### Scenario: Successful listing of registered service providers

- **WHEN** the operator runs `list-service-providers` while the workload
  container is connected and the workload service is running and ready
- **THEN** the charm executes `identity-saml-provider service-provider list
  --format json` with the database connection environment, and sets the
  `service-providers` result to a JSON string array. Each entry contains
  `entity_id`, `acs_url`, and `acs_binding`, plus `attribute_mapping` when
  the provider has one

#### Scenario: Successful listing with no registered service providers

- **WHEN** the operator runs `list-service-providers` and the workload has
  no registered service providers
- **THEN** the charm sets the `service-providers` result to the JSON string
  `[]` and does not fail the action

#### Scenario: Listing fails when workload is not ready

- **WHEN** the operator runs `list-service-providers` while the container is
  disconnected or the workload service is not running or not ready
- **THEN** the charm fails the action indicating that the container or
  workload service is not ready

#### Scenario: Listing fails when the workload CLI fails

- **WHEN** the operator runs `list-service-providers` and the workload CLI
  exits with a non-zero code, returns an error envelope, or returns output
  that is not valid JSON
- **THEN** the charm fails the action with a descriptive error message that
  starts with `Failed to list service providers`
