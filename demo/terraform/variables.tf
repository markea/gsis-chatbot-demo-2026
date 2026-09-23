variable "project_id" {
  description = "GCP Project ID for the GSIS Gabay AI Executive Demo"
  type        = string
  default     = "markea-testbed-dev"
}

variable "region" {
  description = "Primary GCP Region (Singapore)"
  type        = string
  default     = "asia-southeast1"
}

variable "service_name" {
  description = "Cloud Run Service Name"
  type        = string
  default     = "gsis-gabay-ai-demo"
}

variable "container_image" {
  description = "Container image URI in Artifact Registry"
  type        = string
  default     = "asia-southeast1-docker.pkg.dev/markea-testbed-dev/gsis-demo-repo/gsis-gabay-ai-demo:latest"
}
