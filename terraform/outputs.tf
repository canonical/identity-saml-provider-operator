# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "The Juju application name"
  value       = juju_application.application.name
}

//TODO:
output "requires" {
  description = "The Juju integrations that the charm requires"
  value = {
    http-ingress = "http-ingress"
    database     = "database"
    oauth        = "oauth",
    logging      = "logging"
    certificates = "certificates"
  }
}

//TODO:
output "provides" {
  description = "The Juju integrations that the charm provides"
  value = {
    metrics-endpoint  = "metrics-endpoint"
    grafana-dashboard = "grafana-dashboard"
  }
}
