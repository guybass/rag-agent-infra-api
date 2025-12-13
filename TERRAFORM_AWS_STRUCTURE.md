# Terraform AWS Project Structure Guide

> **For**: AI Agents (Claude Code, DevOps Automation Agents)  
> **Provider**: AWS Only  
> **Pattern**: Directory-per-Resource-Kind with Environment Isolation

---

## Directory Structure

```
terraform-infrastructure/
│
├── modules/                              # Reusable modules (NEVER modify directly during apply)
│   │
│   ├── networking/
│   │   ├── vpc/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   └── versions.tf
│   │   │
│   │   ├── subnet/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── internet-gateway/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── nat-gateway/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── route-table/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   └── vpc-endpoint/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   │
│   ├── compute/
│   │   ├── ec2-instance/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── launch-template/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── auto-scaling-group/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── eks-cluster/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── eks-node-group/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── ecs-cluster/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── ecs-service/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   └── lambda-function/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   │
│   ├── database/
│   │   ├── rds-instance/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── rds-cluster/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── dynamodb-table/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   └── elasticache-cluster/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   │
│   ├── storage/
│   │   ├── s3-bucket/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── efs-filesystem/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   └── ebs-volume/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   │
│   ├── security/
│   │   ├── security-group/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── iam-role/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── iam-policy/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── iam-user/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── kms-key/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── secrets-manager/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── acm-certificate/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   └── waf/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   │
│   ├── load-balancing/
│   │   ├── alb/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── nlb/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── target-group/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   └── listener/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   │
│   ├── dns/
│   │   ├── route53-zone/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   └── route53-record/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   │
│   ├── messaging/
│   │   ├── sqs-queue/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   ├── sns-topic/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   │
│   │   └── eventbridge-rule/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   │
│   └── monitoring/
│       ├── cloudwatch-log-group/
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   └── outputs.tf
│       │
│       ├── cloudwatch-alarm/
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   └── outputs.tf
│       │
│       └── cloudwatch-dashboard/
│           ├── main.tf
│           ├── variables.tf
│           └── outputs.tf
│
├── environments/                         # Environment deployments (WHERE you run terraform apply)
│   │
│   ├── dev/
│   │   ├── networking/
│   │   │   ├── main.tf                  # Calls modules with dev config
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   ├── providers.tf
│   │   │   ├── backend.tf
│   │   │   ├── locals.tf
│   │   │   └── terraform.tfvars
│   │   │
│   │   ├── security/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   ├── providers.tf
│   │   │   ├── backend.tf
│   │   │   ├── locals.tf
│   │   │   └── terraform.tfvars
│   │   │
│   │   ├── compute/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   ├── providers.tf
│   │   │   ├── backend.tf
│   │   │   ├── locals.tf
│   │   │   └── terraform.tfvars
│   │   │
│   │   ├── database/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   ├── providers.tf
│   │   │   ├── backend.tf
│   │   │   ├── locals.tf
│   │   │   └── terraform.tfvars
│   │   │
│   │   ├── storage/
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   ├── providers.tf
│   │   │   ├── backend.tf
│   │   │   ├── locals.tf
│   │   │   └── terraform.tfvars
│   │   │
│   │   └── monitoring/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       ├── outputs.tf
│   │       ├── providers.tf
│   │       ├── backend.tf
│   │       ├── locals.tf
│   │       └── terraform.tfvars
│   │
│   ├── staging/
│   │   ├── networking/
│   │   ├── security/
│   │   ├── compute/
│   │   ├── database/
│   │   ├── storage/
│   │   └── monitoring/
│   │
│   └── prod/
│       ├── networking/
│       ├── security/
│       ├── compute/
│       ├── database/
│       ├── storage/
│       └── monitoring/
│
├── global/                               # Resources that exist once across all environments
│   ├── iam/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── backend.tf
│   │   └── terraform.tfvars
│   │
│   ├── route53-zones/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── backend.tf
│   │   └── terraform.tfvars
│   │
│   ├── acm-certificates/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── providers.tf
│   │   ├── backend.tf
│   │   └── terraform.tfvars
│   │
│   └── ecr-repositories/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── providers.tf
│       ├── backend.tf
│       └── terraform.tfvars
│
├── scripts/
│   ├── init.sh
│   ├── plan.sh
│   ├── apply.sh
│   └── destroy.sh
│
├── .gitignore
├── .pre-commit-config.yaml
├── .tflint.hcl
├── Makefile
└── README.md
```

---

## File Templates

### Module: main.tf

Location: `modules/<category>/<resource-kind>/main.tf`

```hcl
# modules/networking/vpc/main.tf

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_hostnames = var.enable_dns_hostnames
  enable_dns_support   = var.enable_dns_support

  tags = merge(var.tags, {
    Name = var.name
  })
}
```

**Rules:**
- One primary resource type per module
- Use `this` as resource name when module creates single instance
- Use descriptive names when module creates multiple related resources
- Never hardcode values - always use variables
- Always merge tags with Name tag

---

### Module: variables.tf

Location: `modules/<category>/<resource-kind>/variables.tf`

```hcl
# modules/networking/vpc/variables.tf

variable "name" {
  description = "Name of the VPC"
  type        = string

  validation {
    condition     = length(var.name) >= 1 && length(var.name) <= 255
    error_message = "Name must be between 1 and 255 characters."
  }
}

variable "cidr_block" {
  description = "CIDR block for the VPC"
  type        = string

  validation {
    condition     = can(cidrhost(var.cidr_block, 0))
    error_message = "Must be a valid CIDR block."
  }
}

variable "enable_dns_hostnames" {
  description = "Enable DNS hostnames in the VPC"
  type        = bool
  default     = true
}

variable "enable_dns_support" {
  description = "Enable DNS support in the VPC"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
```

**Rules:**
- Every variable has `description` and `type`
- Required variables have no `default`
- Optional variables have sensible `default` values
- Add `validation` blocks for input constraints
- `tags` variable is always `map(string)` with `default = {}`

---

### Module: outputs.tf

Location: `modules/<category>/<resource-kind>/outputs.tf`

```hcl
# modules/networking/vpc/outputs.tf

output "id" {
  description = "ID of the VPC"
  value       = aws_vpc.this.id
}

output "arn" {
  description = "ARN of the VPC"
  value       = aws_vpc.this.arn
}

output "cidr_block" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.this.cidr_block
}

output "default_security_group_id" {
  description = "ID of the default security group"
  value       = aws_vpc.this.default_security_group_id
}

output "default_route_table_id" {
  description = "ID of the default route table"
  value       = aws_vpc.this.default_route_table_id
}
```

**Rules:**
- Output every attribute that other resources might reference
- Always include `id` and `arn` when available
- Every output has `description`
- Use short output names (`id` not `vpc_id`) - module name provides context

---

### Module: versions.tf

Location: `modules/<category>/<resource-kind>/versions.tf`

```hcl
# modules/networking/vpc/versions.tf

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0"
    }
  }
}
```

**Rules:**
- Always pin minimum Terraform version
- Always pin minimum provider version
- Use `>=` for modules (allows flexibility)
- Never configure provider in modules (no `provider` block)

---

### Environment: main.tf

Location: `environments/<env>/<resource-kind>/main.tf`

```hcl
# environments/dev/networking/main.tf

module "vpc" {
  source = "../../../modules/networking/vpc"

  name                 = "${local.name_prefix}-vpc"
  cidr_block           = var.vpc_cidr_block
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = local.common_tags
}

module "public_subnets" {
  source   = "../../../modules/networking/subnet"
  for_each = var.public_subnets

  name              = "${local.name_prefix}-public-${each.key}"
  vpc_id            = module.vpc.id
  cidr_block        = each.value.cidr_block
  availability_zone = each.value.availability_zone
  map_public_ip     = true
  tags = merge(local.common_tags, {
    Type = "public"
  })
}

module "private_subnets" {
  source   = "../../../modules/networking/subnet"
  for_each = var.private_subnets

  name              = "${local.name_prefix}-private-${each.key}"
  vpc_id            = module.vpc.id
  cidr_block        = each.value.cidr_block
  availability_zone = each.value.availability_zone
  map_public_ip     = false
  tags = merge(local.common_tags, {
    Type = "private"
  })
}

module "internet_gateway" {
  source = "../../../modules/networking/internet-gateway"

  name   = "${local.name_prefix}-igw"
  vpc_id = module.vpc.id
  tags   = local.common_tags
}

module "nat_gateways" {
  source   = "../../../modules/networking/nat-gateway"
  for_each = var.nat_gateways

  name      = "${local.name_prefix}-nat-${each.key}"
  subnet_id = module.public_subnets[each.value.public_subnet_key].id
  tags      = local.common_tags
}
```

**Rules:**
- Call modules using relative paths `../../../modules/`
- Use `for_each` for multiple instances of same resource type
- Construct names using `local.name_prefix`
- Always pass `local.common_tags`
- Chain module outputs as inputs to dependent modules

---

### Environment: variables.tf

Location: `environments/<env>/<resource-kind>/variables.tf`

```hcl
# environments/dev/networking/variables.tf

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project" {
  description = "Project name"
  type        = string
}

variable "owner" {
  description = "Owner email for tagging"
  type        = string
}

variable "vpc_cidr_block" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "public_subnets" {
  description = "Map of public subnet configurations"
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
}

variable "private_subnets" {
  description = "Map of private subnet configurations"
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
}

variable "nat_gateways" {
  description = "Map of NAT gateway configurations"
  type = map(object({
    public_subnet_key = string
  }))
}
```

**Rules:**
- Always include `aws_region`, `environment`, `project`, `owner`
- Use `map(object({}))` for resources that need multiple instances
- Complex types prevent configuration errors
- No defaults for environment-specific values

---

### Environment: outputs.tf

Location: `environments/<env>/<resource-kind>/outputs.tf`

```hcl
# environments/dev/networking/outputs.tf

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = module.vpc.cidr_block
}

output "public_subnet_ids" {
  description = "Map of public subnet IDs"
  value       = { for k, v in module.public_subnets : k => v.id }
}

output "private_subnet_ids" {
  description = "Map of private subnet IDs"
  value       = { for k, v in module.private_subnets : k => v.id }
}

output "nat_gateway_ids" {
  description = "Map of NAT gateway IDs"
  value       = { for k, v in module.nat_gateways : k => v.id }
}

output "internet_gateway_id" {
  description = "ID of the internet gateway"
  value       = module.internet_gateway.id
}
```

**Rules:**
- Output all values needed by other environment components
- Use maps for multiple resources to preserve keys
- These outputs are read by other components via `terraform_remote_state`

---

### Environment: providers.tf

Location: `environments/<env>/<resource-kind>/providers.tf`

```hcl
# environments/dev/networking/providers.tf

terraform {
  required_version = "~> 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project
      ManagedBy   = "terraform"
      Owner       = var.owner
    }
  }
}
```

**Rules:**
- Pin exact Terraform version with `~>` (allows patch updates only)
- Pin exact provider version with `~>` (allows patch updates only)
- Use `default_tags` - applies to ALL resources automatically
- Provider configuration exists ONLY in environment files, never in modules

---

### Environment: backend.tf

Location: `environments/<env>/<resource-kind>/backend.tf`

```hcl
# environments/dev/networking/backend.tf

terraform {
  backend "s3" {
    bucket         = "company-terraform-state"
    key            = "dev/networking/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

**Rules:**
- State key pattern: `<environment>/<resource-kind>/terraform.tfstate`
- Always enable encryption
- Always use DynamoDB for state locking
- Same S3 bucket for all environments (different keys)
- Same DynamoDB table for all environments

---

### Environment: locals.tf

Location: `environments/<env>/<resource-kind>/locals.tf`

```hcl
# environments/dev/networking/locals.tf

locals {
  name_prefix = "${var.project}-${var.environment}"

  common_tags = {
    Environment = var.environment
    Project     = var.project
    ManagedBy   = "terraform"
    Owner       = var.owner
    Component   = "networking"
  }
}

# Remote state data sources for cross-component references
data "terraform_remote_state" "security" {
  backend = "s3"

  config = {
    bucket = "company-terraform-state"
    key    = "${var.environment}/security/terraform.tfstate"
    region = "us-east-1"
  }
}
```

**Rules:**
- `name_prefix` follows pattern `<project>-<environment>`
- `common_tags` includes Component to identify resource-kind
- Use `terraform_remote_state` to read outputs from other components
- Data sources for remote state go in locals.tf

---

### Environment: terraform.tfvars

Location: `environments/<env>/<resource-kind>/terraform.tfvars`

```hcl
# environments/dev/networking/terraform.tfvars

aws_region  = "us-east-1"
environment = "dev"
project     = "myproject"
owner       = "team@company.com"

vpc_cidr_block = "10.0.0.0/16"

public_subnets = {
  "a" = {
    cidr_block        = "10.0.1.0/24"
    availability_zone = "us-east-1a"
  }
  "b" = {
    cidr_block        = "10.0.2.0/24"
    availability_zone = "us-east-1b"
  }
  "c" = {
    cidr_block        = "10.0.3.0/24"
    availability_zone = "us-east-1c"
  }
}

private_subnets = {
  "a" = {
    cidr_block        = "10.0.11.0/24"
    availability_zone = "us-east-1a"
  }
  "b" = {
    cidr_block        = "10.0.12.0/24"
    availability_zone = "us-east-1b"
  }
  "c" = {
    cidr_block        = "10.0.13.0/24"
    availability_zone = "us-east-1c"
  }
}

nat_gateways = {
  "a" = {
    public_subnet_key = "a"
  }
}
```

**Rules:**
- No secrets in tfvars files
- Use consistent map keys across related resources
- Environment differences expressed through different values
- This file is committed to git (no secrets)

---

## Cross-Component References

When one component needs outputs from another component, use `terraform_remote_state`:

```hcl
# environments/dev/compute/locals.tf

data "terraform_remote_state" "networking" {
  backend = "s3"
  config = {
    bucket = "company-terraform-state"
    key    = "${var.environment}/networking/terraform.tfstate"
    region = "us-east-1"
  }
}

data "terraform_remote_state" "security" {
  backend = "s3"
  config = {
    bucket = "company-terraform-state"
    key    = "${var.environment}/security/terraform.tfstate"
    region = "us-east-1"
  }
}

# environments/dev/compute/main.tf

module "web_instances" {
  source = "../../../modules/compute/ec2-instance"

  name               = "${local.name_prefix}-web"
  instance_type      = var.instance_type
  subnet_id          = data.terraform_remote_state.networking.outputs.private_subnet_ids["a"]
  security_group_ids = [data.terraform_remote_state.security.outputs.web_security_group_id]
  tags               = local.common_tags
}
```

---

## Deployment Order

Components must be deployed in dependency order:

```
1. global/iam                    # IAM roles used across environments
2. global/route53-zones          # DNS zones
3. global/acm-certificates       # SSL certificates
4. global/ecr-repositories       # Container registries

5. environments/<env>/security   # Security groups, KMS keys
6. environments/<env>/networking # VPC, subnets, gateways
7. environments/<env>/storage    # S3, EFS
8. environments/<env>/database   # RDS, DynamoDB
9. environments/<env>/compute    # EC2, EKS, ECS, Lambda
10. environments/<env>/monitoring # CloudWatch, alarms
```

**Apply command pattern:**

```bash
cd environments/dev/networking
terraform init
terraform plan
terraform apply
```

---

## State Key Convention

All state files follow this pattern:

```
s3://company-terraform-state/
├── global/
│   ├── iam/terraform.tfstate
│   ├── route53-zones/terraform.tfstate
│   ├── acm-certificates/terraform.tfstate
│   └── ecr-repositories/terraform.tfstate
│
├── dev/
│   ├── networking/terraform.tfstate
│   ├── security/terraform.tfstate
│   ├── compute/terraform.tfstate
│   ├── database/terraform.tfstate
│   ├── storage/terraform.tfstate
│   └── monitoring/terraform.tfstate
│
├── staging/
│   ├── networking/terraform.tfstate
│   ├── security/terraform.tfstate
│   └── ...
│
└── prod/
    ├── networking/terraform.tfstate
    ├── security/terraform.tfstate
    └── ...
```

---

## Naming Conventions

### Resource Names in AWS

Pattern: `<project>-<environment>-<component>-<identifier>`

```
myproject-dev-vpc
myproject-dev-public-subnet-a
myproject-dev-private-subnet-a
myproject-dev-web-sg
myproject-dev-web-instance
myproject-dev-app-alb
myproject-prod-db-primary
```

### Terraform Resource Names

```hcl
# In modules - use 'this' for single resource
resource "aws_vpc" "this" { }

# In modules - use descriptive names for multiple
resource "aws_subnet" "public" { }
resource "aws_subnet" "private" { }

# In environments - use the module name as context
module "vpc" { }
module "public_subnets" { }
module "web_security_group" { }
```

### Variable Names

```hcl
# Include units
variable "disk_size_gb" { }
variable "memory_mb" { }
variable "timeout_seconds" { }

# Boolean - positive form
variable "enable_encryption" { }
variable "enable_monitoring" { }

# Lists
variable "subnet_ids" { }
variable "security_group_ids" { }

# Maps
variable "public_subnets" { }
variable "tags" { }
```

---

## .gitignore

```gitignore
# Terraform
**/.terraform/*
*.tfstate
*.tfstate.*
crash.log
crash.*.log
*.tfvars.json
override.tf
override.tf.json
*_override.tf
*_override.tf.json
.terraformrc
terraform.rc
*.tfplan

# Keep .terraform.lock.hcl (provider lock file)
!.terraform.lock.hcl

# Environment
.env
.env.*

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

---

## Common Module Examples

### Security Group Module

```hcl
# modules/security/security-group/main.tf

resource "aws_security_group" "this" {
  name        = var.name
  description = var.description
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = var.name
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "this" {
  for_each = var.ingress_rules

  security_group_id = aws_security_group.this.id
  description       = each.value.description

  ip_protocol = each.value.protocol
  from_port   = each.value.from_port
  to_port     = each.value.to_port

  cidr_ipv4                    = lookup(each.value, "cidr_ipv4", null)
  referenced_security_group_id = lookup(each.value, "source_security_group_id", null)

  tags = var.tags
}

resource "aws_vpc_security_group_egress_rule" "this" {
  for_each = var.egress_rules

  security_group_id = aws_security_group.this.id
  description       = each.value.description

  ip_protocol = each.value.protocol
  from_port   = each.value.from_port
  to_port     = each.value.to_port

  cidr_ipv4                    = lookup(each.value, "cidr_ipv4", null)
  referenced_security_group_id = lookup(each.value, "destination_security_group_id", null)

  tags = var.tags
}

# modules/security/security-group/variables.tf

variable "name" {
  description = "Name of the security group"
  type        = string
}

variable "description" {
  description = "Description of the security group"
  type        = string
  default     = "Managed by Terraform"
}

variable "vpc_id" {
  description = "VPC ID where the security group will be created"
  type        = string
}

variable "ingress_rules" {
  description = "Map of ingress rules"
  type = map(object({
    description              = string
    protocol                 = string
    from_port                = number
    to_port                  = number
    cidr_ipv4                = optional(string)
    source_security_group_id = optional(string)
  }))
  default = {}
}

variable "egress_rules" {
  description = "Map of egress rules"
  type = map(object({
    description                   = string
    protocol                      = string
    from_port                     = number
    to_port                       = number
    cidr_ipv4                     = optional(string)
    destination_security_group_id = optional(string)
  }))
  default = {
    all_outbound = {
      description = "Allow all outbound traffic"
      protocol    = "-1"
      from_port   = 0
      to_port     = 0
      cidr_ipv4   = "0.0.0.0/0"
    }
  }
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# modules/security/security-group/outputs.tf

output "id" {
  description = "ID of the security group"
  value       = aws_security_group.this.id
}

output "arn" {
  description = "ARN of the security group"
  value       = aws_security_group.this.arn
}

output "name" {
  description = "Name of the security group"
  value       = aws_security_group.this.name
}
```

---

### S3 Bucket Module

```hcl
# modules/storage/s3-bucket/main.tf

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name

  tags = merge(var.tags, {
    Name = var.bucket_name
  })
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.kms_key_arn != null ? "aws:kms" : "AES256"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = var.kms_key_arn != null
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  count  = length(var.lifecycle_rules) > 0 ? 1 : 0
  bucket = aws_s3_bucket.this.id

  dynamic "rule" {
    for_each = var.lifecycle_rules
    content {
      id     = rule.key
      status = "Enabled"

      filter {
        prefix = lookup(rule.value, "prefix", "")
      }

      dynamic "transition" {
        for_each = lookup(rule.value, "transitions", [])
        content {
          days          = transition.value.days
          storage_class = transition.value.storage_class
        }
      }

      dynamic "expiration" {
        for_each = lookup(rule.value, "expiration_days", null) != null ? [1] : []
        content {
          days = rule.value.expiration_days
        }
      }
    }
  }
}

# modules/storage/s3-bucket/variables.tf

variable "bucket_name" {
  description = "Name of the S3 bucket"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.bucket_name))
    error_message = "Bucket name must be valid S3 bucket name."
  }
}

variable "enable_versioning" {
  description = "Enable versioning on the bucket"
  type        = bool
  default     = true
}

variable "kms_key_arn" {
  description = "KMS key ARN for server-side encryption (null for AES256)"
  type        = string
  default     = null
}

variable "lifecycle_rules" {
  description = "Map of lifecycle rules"
  type = map(object({
    prefix          = optional(string, "")
    expiration_days = optional(number)
    transitions = optional(list(object({
      days          = number
      storage_class = string
    })), [])
  }))
  default = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# modules/storage/s3-bucket/outputs.tf

output "id" {
  description = "ID of the S3 bucket"
  value       = aws_s3_bucket.this.id
}

output "arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.this.arn
}

output "bucket_domain_name" {
  description = "Bucket domain name"
  value       = aws_s3_bucket.this.bucket_domain_name
}

output "bucket_regional_domain_name" {
  description = "Bucket regional domain name"
  value       = aws_s3_bucket.this.bucket_regional_domain_name
}
```

---

## Agent Instructions

### Creating New Module

1. Identify category: `networking`, `compute`, `database`, `storage`, `security`, `load-balancing`, `dns`, `messaging`, `monitoring`
2. Create directory: `modules/<category>/<resource-kind>/`
3. Create files: `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`
4. Follow templates exactly
5. Use `this` for single resource name
6. Output all useful attributes

### Creating New Environment Component

1. Create directory: `environments/<env>/<resource-kind>/`
2. Create files: `main.tf`, `variables.tf`, `outputs.tf`, `providers.tf`, `backend.tf`, `locals.tf`, `terraform.tfvars`
3. Set backend key: `<env>/<resource-kind>/terraform.tfstate`
4. Add remote state data sources for dependencies
5. Call modules with environment-specific values

### Deploying Changes

```bash
# Navigate to component
cd environments/<env>/<resource-kind>

# Initialize
terraform init

# Plan (always review)
terraform plan

# Apply
terraform apply
```

### Adding Resource to Existing Component

1. Add module call to component's `main.tf`
2. Add required variables to `variables.tf`
3. Add values to `terraform.tfvars`
4. Add outputs to `outputs.tf`
5. Run `terraform plan` to verify
6. Run `terraform apply` to create

### Modifying Module

1. Edit module files in `modules/<category>/<resource-kind>/`
2. Test in dev environment first
3. Run `terraform plan` in each environment using the module
4. Apply changes environment by environment: dev → staging → prod

---

## Quick Reference

### File Locations

| Need | Location |
|------|----------|
| Create reusable resource | `modules/<category>/<resource-kind>/` |
| Deploy to environment | `environments/<env>/<resource-kind>/` |
| Global resources | `global/<resource-kind>/` |
| Run terraform apply | `environments/<env>/<resource-kind>/` |

### State Key Format

```
<environment>/<resource-kind>/terraform.tfstate
```

### Name Prefix Format

```
<project>-<environment>
```

### Tag Requirements

```hcl
{
  Environment = var.environment
  Project     = var.project
  ManagedBy   = "terraform"
  Owner       = var.owner
  Component   = "<resource-kind>"
}
```

---

> **Version**: 2.0  
> **Pattern**: Directory-per-Resource-Kind with Environment Isolation  
> **Provider**: AWS  
> **For**: AI Agent Use Only
