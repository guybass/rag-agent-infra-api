import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

try:
    import hcl2
    HCL2_AVAILABLE = True
except ImportError:
    HCL2_AVAILABLE = False

from app.models.index_schemas import (
    TerraformResource,
    TerraformModuleCall,
    TerraformParseResult,
    TerraformCategory,
)


class TerraformParser:
    """
    Parses Terraform HCL files to extract structured information
    for indexing and semantic search.
    """

    # Mapping of resource type prefixes to categories
    RESOURCE_CATEGORY_MAP = {
        "aws_vpc": TerraformCategory.NETWORKING,
        "aws_subnet": TerraformCategory.NETWORKING,
        "aws_internet_gateway": TerraformCategory.NETWORKING,
        "aws_nat_gateway": TerraformCategory.NETWORKING,
        "aws_route": TerraformCategory.NETWORKING,
        "aws_route_table": TerraformCategory.NETWORKING,
        "aws_vpc_endpoint": TerraformCategory.NETWORKING,
        "aws_eip": TerraformCategory.NETWORKING,

        "aws_instance": TerraformCategory.COMPUTE,
        "aws_launch_template": TerraformCategory.COMPUTE,
        "aws_autoscaling": TerraformCategory.COMPUTE,
        "aws_eks": TerraformCategory.COMPUTE,
        "aws_ecs": TerraformCategory.COMPUTE,
        "aws_lambda": TerraformCategory.COMPUTE,

        "aws_db": TerraformCategory.DATABASE,
        "aws_rds": TerraformCategory.DATABASE,
        "aws_dynamodb": TerraformCategory.DATABASE,
        "aws_elasticache": TerraformCategory.DATABASE,

        "aws_s3": TerraformCategory.STORAGE,
        "aws_efs": TerraformCategory.STORAGE,
        "aws_ebs": TerraformCategory.STORAGE,

        "aws_security_group": TerraformCategory.SECURITY,
        "aws_iam": TerraformCategory.SECURITY,
        "aws_kms": TerraformCategory.SECURITY,
        "aws_secretsmanager": TerraformCategory.SECURITY,
        "aws_acm": TerraformCategory.SECURITY,
        "aws_waf": TerraformCategory.SECURITY,

        "aws_lb": TerraformCategory.LOAD_BALANCING,
        "aws_alb": TerraformCategory.LOAD_BALANCING,
        "aws_elb": TerraformCategory.LOAD_BALANCING,

        "aws_route53": TerraformCategory.DNS,

        "aws_sqs": TerraformCategory.MESSAGING,
        "aws_sns": TerraformCategory.MESSAGING,
        "aws_eventbridge": TerraformCategory.MESSAGING,

        "aws_cloudwatch": TerraformCategory.MONITORING,
    }

    # AWS service name extraction
    AWS_SERVICE_PATTERNS = {
        "ec2": ["aws_instance", "aws_launch_template", "aws_ami"],
        "eks": ["aws_eks"],
        "ecs": ["aws_ecs"],
        "lambda": ["aws_lambda"],
        "rds": ["aws_db_instance", "aws_rds"],
        "dynamodb": ["aws_dynamodb"],
        "s3": ["aws_s3"],
        "vpc": ["aws_vpc", "aws_subnet", "aws_route"],
        "iam": ["aws_iam"],
        "kms": ["aws_kms"],
        "alb": ["aws_lb", "aws_alb"],
        "route53": ["aws_route53"],
        "cloudwatch": ["aws_cloudwatch"],
        "sqs": ["aws_sqs"],
        "sns": ["aws_sns"],
    }

    def __init__(self):
        self.use_hcl2 = HCL2_AVAILABLE

    def parse_file(self, content: str, file_path: str) -> TerraformParseResult:
        """
        Parse a terraform file and extract all relevant information.

        Args:
            content: File content
            file_path: Path to the file

        Returns:
            TerraformParseResult with extracted data
        """
        file_type = self._determine_file_type(file_path)

        result = TerraformParseResult(
            file_path=file_path,
            file_type=file_type,
        )

        if self.use_hcl2:
            result = self._parse_with_hcl2(content, file_path, result)
        else:
            result = self._parse_with_regex(content, file_path, result)

        return result

    def _determine_file_type(self, file_path: str) -> str:
        """Determine the type of terraform file."""
        name = Path(file_path).name.lower()

        if name == "main.tf":
            return "main.tf"
        elif name == "variables.tf":
            return "variables.tf"
        elif name == "outputs.tf":
            return "outputs.tf"
        elif name == "providers.tf":
            return "providers.tf"
        elif name == "backend.tf":
            return "backend.tf"
        elif name == "locals.tf":
            return "locals.tf"
        elif name == "versions.tf":
            return "versions.tf"
        elif name.endswith(".tfvars"):
            return "terraform.tfvars"
        elif name.endswith(".tf"):
            return "terraform"
        else:
            return "unknown"

    def _parse_with_hcl2(
        self,
        content: str,
        file_path: str,
        result: TerraformParseResult,
    ) -> TerraformParseResult:
        """Parse using python-hcl2 library."""
        try:
            import io
            parsed = hcl2.load(io.StringIO(content))

            # Extract resources
            if "resource" in parsed:
                for resource_block in parsed["resource"]:
                    for resource_type, resources in resource_block.items():
                        for resource_name, attrs in resources.items():
                            result.resources.append(TerraformResource(
                                resource_type=resource_type,
                                resource_name=resource_name,
                                provider=self._extract_provider(resource_type),
                                attributes=attrs if isinstance(attrs, dict) else {},
                                file_path=file_path,
                            ))

            # Extract variables
            if "variable" in parsed:
                for var_block in parsed["variable"]:
                    for var_name, var_config in var_block.items():
                        result.variables.append({
                            "name": var_name,
                            "type": var_config.get("type", "any"),
                            "description": var_config.get("description", ""),
                            "default": var_config.get("default"),
                        })

            # Extract outputs
            if "output" in parsed:
                for output_block in parsed["output"]:
                    for output_name, output_config in output_block.items():
                        result.outputs.append({
                            "name": output_name,
                            "description": output_config.get("description", ""),
                            "value": str(output_config.get("value", "")),
                        })

            # Extract module calls
            if "module" in parsed:
                for module_block in parsed["module"]:
                    for module_name, module_config in module_block.items():
                        result.module_calls.append(TerraformModuleCall(
                            module_name=module_name,
                            source=module_config.get("source", ""),
                            variables={k: v for k, v in module_config.items() if k != "source"},
                            file_path=file_path,
                        ))

            # Extract data sources
            if "data" in parsed:
                for data_block in parsed["data"]:
                    for data_type, data_resources in data_block.items():
                        for data_name, data_config in data_resources.items():
                            result.data_sources.append({
                                "type": data_type,
                                "name": data_name,
                                "config": data_config,
                            })

            # Extract locals
            if "locals" in parsed:
                for locals_block in parsed["locals"]:
                    result.locals.update(locals_block)

            # Extract providers
            if "provider" in parsed:
                for provider_block in parsed["provider"]:
                    for provider_name, provider_config in provider_block.items():
                        result.providers.append({
                            "name": provider_name,
                            "config": provider_config,
                        })

        except Exception:
            # Fall back to regex parsing
            return self._parse_with_regex(content, file_path, result)

        return result

    def _parse_with_regex(
        self,
        content: str,
        file_path: str,
        result: TerraformParseResult,
    ) -> TerraformParseResult:
        """Parse using regex patterns (fallback)."""

        # Extract resources
        resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{'
        for match in re.finditer(resource_pattern, content):
            resource_type = match.group(1)
            resource_name = match.group(2)
            result.resources.append(TerraformResource(
                resource_type=resource_type,
                resource_name=resource_name,
                provider=self._extract_provider(resource_type),
                attributes={},
                file_path=file_path,
                line_number=content[:match.start()].count('\n') + 1,
            ))

        # Extract variables
        variable_pattern = r'variable\s+"([^"]+)"\s*\{'
        for match in re.finditer(variable_pattern, content):
            var_name = match.group(1)
            # Try to extract description
            desc_match = re.search(
                rf'variable\s+"{var_name}"\s*\{{[^}}]*description\s*=\s*"([^"]*)"',
                content,
                re.DOTALL,
            )
            result.variables.append({
                "name": var_name,
                "description": desc_match.group(1) if desc_match else "",
            })

        # Extract outputs
        output_pattern = r'output\s+"([^"]+)"\s*\{'
        for match in re.finditer(output_pattern, content):
            output_name = match.group(1)
            result.outputs.append({"name": output_name})

        # Extract module calls
        module_pattern = r'module\s+"([^"]+)"\s*\{[^}]*source\s*=\s*"([^"]+)"'
        for match in re.finditer(module_pattern, content, re.DOTALL):
            module_name = match.group(1)
            source = match.group(2)
            result.module_calls.append(TerraformModuleCall(
                module_name=module_name,
                source=source,
                variables={},
                file_path=file_path,
            ))

        # Extract data sources
        data_pattern = r'data\s+"([^"]+)"\s+"([^"]+)"\s*\{'
        for match in re.finditer(data_pattern, content):
            result.data_sources.append({
                "type": match.group(1),
                "name": match.group(2),
            })

        return result

    def _extract_provider(self, resource_type: str) -> str:
        """Extract provider name from resource type."""
        parts = resource_type.split("_")
        return parts[0] if parts else "unknown"

    def get_category_for_resource(self, resource_type: str) -> Optional[str]:
        """Get the category for a resource type."""
        for prefix, category in self.RESOURCE_CATEGORY_MAP.items():
            if resource_type.startswith(prefix):
                return category.value
        return None

    def get_aws_services(self, resource_types: List[str]) -> List[str]:
        """Extract AWS service names from resource types."""
        services = set()
        for resource_type in resource_types:
            for service, patterns in self.AWS_SERVICE_PATTERNS.items():
                for pattern in patterns:
                    if resource_type.startswith(pattern):
                        services.add(service)
                        break
        return list(services)

    def determine_category_from_path(self, file_path: str) -> Optional[str]:
        """
        Determine category from file path based on TERRAFORM_AWS_STRUCTURE.md.

        Expected paths like:
        - modules/networking/vpc/main.tf -> networking
        - environments/dev/compute/main.tf -> compute
        """
        path_lower = file_path.lower()
        path_parts = Path(path_lower).parts

        # Check for category directories
        categories = [c.value for c in TerraformCategory]
        for part in path_parts:
            if part in categories:
                return part

        # Check for known patterns
        category_keywords = {
            "networking": ["vpc", "subnet", "gateway", "route"],
            "compute": ["ec2", "eks", "ecs", "lambda", "instance"],
            "database": ["rds", "dynamodb", "elasticache", "db"],
            "storage": ["s3", "efs", "ebs"],
            "security": ["iam", "security", "kms", "secret", "acm", "waf"],
            "load-balancing": ["alb", "nlb", "elb", "lb", "load"],
            "dns": ["route53", "dns"],
            "messaging": ["sqs", "sns", "eventbridge"],
            "monitoring": ["cloudwatch", "monitoring", "alarm"],
        }

        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in path_lower:
                    return category

        return None

    def determine_environment_from_path(self, file_path: str) -> Optional[str]:
        """
        Determine environment from file path.

        Expected paths like:
        - environments/dev/networking/main.tf -> dev
        - environments/prod/compute/main.tf -> prod
        """
        path_lower = file_path.lower()
        path_parts = Path(path_lower).parts

        environments = ["dev", "staging", "prod", "production", "test", "qa"]
        for part in path_parts:
            if part in environments:
                return "prod" if part == "production" else part

        # Check for global
        if "global" in path_parts:
            return "global"

        return None

    def is_module_file(self, file_path: str) -> bool:
        """Check if file is in a modules directory."""
        return "modules" in Path(file_path).parts

    def extract_resource_kind_from_path(self, file_path: str) -> Optional[str]:
        """
        Extract resource kind from path.

        Expected paths like:
        - modules/networking/vpc/main.tf -> vpc
        - modules/compute/eks-cluster/variables.tf -> eks-cluster
        """
        path = Path(file_path)
        parts = path.parts

        # Look for the directory right before the filename
        if len(parts) >= 2:
            parent_dir = parts[-2]
            # Check if it's not a category or environment
            categories = [c.value for c in TerraformCategory]
            environments = ["dev", "staging", "prod", "global", "environments", "modules"]

            if parent_dir not in categories and parent_dir not in environments:
                return parent_dir

        return None
