import json
from typing import List, Dict, Any, Optional

from app.models.index_schemas import StateResource, CloudResource


class TerraformStateParser:
    """
    Parses Terraform state files (terraform.tfstate) to extract resource information.
    """

    def parse_state_file(self, content: str) -> List[StateResource]:
        """
        Parse a terraform.tfstate file.

        Args:
            content: JSON content of the state file

        Returns:
            List of StateResource objects
        """
        try:
            state = json.loads(content)
        except json.JSONDecodeError:
            return []

        version = state.get("version", 4)

        if version >= 4:
            return self._parse_v4_state(state)
        else:
            return self._parse_v3_state(state)

    def _parse_v4_state(self, state: Dict[str, Any]) -> List[StateResource]:
        """Parse Terraform state version 4."""
        resources = []

        for resource in state.get("resources", []):
            resource_type = resource.get("type", "")
            resource_name = resource.get("name", "")
            mode = resource.get("mode", "managed")
            provider = resource.get("provider", "")

            # Extract provider name
            if "provider[" in provider:
                provider = provider.split("[")[1].split("]")[0].strip('"')

            instances = []
            for instance in resource.get("instances", []):
                attrs = instance.get("attributes", {})
                instances.append(attrs)

            resources.append(StateResource(
                resource_type=resource_type,
                resource_name=resource_name,
                resource_mode=mode,
                provider=provider,
                instances=instances,
            ))

        return resources

    def _parse_v3_state(self, state: Dict[str, Any]) -> List[StateResource]:
        """Parse Terraform state version 3 and below."""
        resources = []

        modules = state.get("modules", [])
        for module in modules:
            for resource_key, resource_data in module.get("resources", {}).items():
                # Parse resource key (e.g., "aws_instance.example")
                parts = resource_key.split(".")
                if len(parts) >= 2:
                    resource_type = parts[0]
                    resource_name = ".".join(parts[1:])
                else:
                    resource_type = resource_key
                    resource_name = "unknown"

                provider = resource_data.get("provider", "")
                primary = resource_data.get("primary", {})
                attrs = primary.get("attributes", {})

                resources.append(StateResource(
                    resource_type=resource_type,
                    resource_name=resource_name,
                    resource_mode=resource_data.get("type", "managed"),
                    provider=provider,
                    instances=[attrs],
                ))

        return resources

    def state_to_cloud_resources(
        self,
        state_resources: List[StateResource],
        region: str = "unknown",
    ) -> List[CloudResource]:
        """
        Convert StateResources to CloudResources.

        Args:
            state_resources: Parsed state resources
            region: AWS region

        Returns:
            List of CloudResource objects
        """
        cloud_resources = []

        for sr in state_resources:
            for instance in sr.instances:
                # Extract common attributes
                resource_id = instance.get("id", "")
                resource_arn = instance.get("arn", "")
                resource_name = instance.get("name") or instance.get("tags", {}).get("Name", sr.resource_name)
                tags = instance.get("tags", {})

                # Handle tags that might be a string
                if isinstance(tags, str):
                    tags = {}

                cloud_resources.append(CloudResource(
                    resource_type=sr.resource_type,
                    resource_id=resource_id,
                    resource_arn=resource_arn,
                    resource_name=resource_name,
                    region=instance.get("region", region),
                    state_data=instance,
                    tags=tags if isinstance(tags, dict) else {},
                ))

        return cloud_resources

    def extract_resource_ids(self, state_resources: List[StateResource]) -> Dict[str, List[str]]:
        """
        Extract resource IDs grouped by type.

        Args:
            state_resources: Parsed state resources

        Returns:
            Dict mapping resource types to lists of IDs
        """
        result = {}

        for sr in state_resources:
            if sr.resource_type not in result:
                result[sr.resource_type] = []

            for instance in sr.instances:
                resource_id = instance.get("id", "")
                if resource_id:
                    result[sr.resource_type].append(resource_id)

        return result

    def get_resource_by_id(
        self,
        state_resources: List[StateResource],
        resource_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a resource by its ID.

        Args:
            state_resources: Parsed state resources
            resource_id: Resource ID to find

        Returns:
            Resource attributes or None
        """
        for sr in state_resources:
            for instance in sr.instances:
                if instance.get("id") == resource_id:
                    return {
                        "resource_type": sr.resource_type,
                        "resource_name": sr.resource_name,
                        "provider": sr.provider,
                        "attributes": instance,
                    }

        return None

    def get_resource_dependencies(
        self,
        state_resources: List[StateResource],
        resource_type: str,
        resource_name: str,
    ) -> List[str]:
        """
        Find dependencies for a resource.

        Note: This requires the full state with dependencies, which
        may not always be available.

        Args:
            state_resources: Parsed state resources
            resource_type: Type of resource
            resource_name: Name of resource

        Returns:
            List of dependency references
        """
        # In v4 state, dependencies are tracked per instance
        for sr in state_resources:
            if sr.resource_type == resource_type and sr.resource_name == resource_name:
                deps = set()
                for instance in sr.instances:
                    # Look for common dependency patterns
                    attrs = instance
                    for key, value in attrs.items():
                        if isinstance(value, str):
                            # Look for resource references
                            if value.startswith("arn:aws:"):
                                deps.add(value)
                            elif key.endswith("_id") and value:
                                deps.add(f"{key}={value}")
                return list(deps)

        return []
