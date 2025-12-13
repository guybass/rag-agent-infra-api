import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from app.models.index_schemas import CloudResource
from app.config import get_settings


class AWSResourceFetcher:
    """
    Fetches live resource state from AWS APIs.
    Supports major AWS services used in Terraform deployments.
    """

    SUPPORTED_RESOURCE_TYPES = [
        "ec2",
        "vpc",
        "subnet",
        "security_group",
        "eks",
        "rds",
        "s3",
        "iam_role",
        "lambda",
        "alb",
        "nlb",
        "route53",
        "dynamodb",
        "elasticache",
        "ecs",
    ]

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region: Optional[str] = None,
    ):
        settings = get_settings()
        self.default_region = region or settings.aws_region

        self.credentials = {}
        if aws_access_key_id and aws_secret_access_key:
            self.credentials = {
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key,
            }
        elif settings.aws_access_key_id and settings.aws_secret_access_key:
            self.credentials = {
                "aws_access_key_id": settings.aws_access_key_id,
                "aws_secret_access_key": settings.aws_secret_access_key,
            }

        self.config = Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

    def _get_client(self, service: str, region: str):
        """Get boto3 client for a service."""
        return boto3.client(
            service,
            region_name=region,
            config=self.config,
            **self.credentials,
        )

    async def fetch_resources(
        self,
        resource_type: str,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """
        Fetch resources of a specific type.

        Args:
            resource_type: Type of resource (ec2, vpc, etc.)
            region: AWS region
            filters: Optional filters

        Returns:
            List of CloudResource objects
        """
        fetcher_method = getattr(self, f"_fetch_{resource_type}", None)
        if not fetcher_method:
            return []

        try:
            return await asyncio.to_thread(fetcher_method, region, filters)
        except (ClientError, NoCredentialsError) as e:
            # Log error but don't fail
            return []

    async def fetch_all_resources(
        self,
        resource_types: List[str],
        region: str,
    ) -> Dict[str, List[CloudResource]]:
        """
        Fetch multiple resource types in parallel.

        Args:
            resource_types: Types to fetch
            region: AWS region

        Returns:
            Dict mapping types to resources
        """
        tasks = [
            self.fetch_resources(rt, region)
            for rt in resource_types
            if rt in self.SUPPORTED_RESOURCE_TYPES
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for i, rt in enumerate(resource_types):
            if rt in self.SUPPORTED_RESOURCE_TYPES:
                result = results[i] if i < len(results) else []
                if isinstance(result, list):
                    output[rt] = result
                else:
                    output[rt] = []

        return output

    # ========================================================================
    # Individual Resource Fetchers
    # ========================================================================

    def _fetch_ec2(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch EC2 instances."""
        ec2 = self._get_client("ec2", region)
        resources = []

        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page["Reservations"]:
                for instance in reservation["Instances"]:
                    tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
                    resources.append(CloudResource(
                        resource_type="aws_instance",
                        resource_id=instance["InstanceId"],
                        resource_arn=f"arn:aws:ec2:{region}::instance/{instance['InstanceId']}",
                        resource_name=tags.get("Name", instance["InstanceId"]),
                        region=region,
                        state_data={
                            "instance_type": instance.get("InstanceType"),
                            "state": instance.get("State", {}).get("Name"),
                            "vpc_id": instance.get("VpcId"),
                            "subnet_id": instance.get("SubnetId"),
                            "private_ip": instance.get("PrivateIpAddress"),
                            "public_ip": instance.get("PublicIpAddress"),
                        },
                        tags=tags,
                    ))

        return resources

    def _fetch_vpc(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch VPCs."""
        ec2 = self._get_client("ec2", region)
        resources = []

        response = ec2.describe_vpcs()
        for vpc in response["Vpcs"]:
            tags = {t["Key"]: t["Value"] for t in vpc.get("Tags", [])}
            resources.append(CloudResource(
                resource_type="aws_vpc",
                resource_id=vpc["VpcId"],
                resource_arn=f"arn:aws:ec2:{region}::vpc/{vpc['VpcId']}",
                resource_name=tags.get("Name", vpc["VpcId"]),
                region=region,
                state_data={
                    "cidr_block": vpc.get("CidrBlock"),
                    "state": vpc.get("State"),
                    "is_default": vpc.get("IsDefault"),
                },
                tags=tags,
            ))

        return resources

    def _fetch_subnet(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch subnets."""
        ec2 = self._get_client("ec2", region)
        resources = []

        response = ec2.describe_subnets()
        for subnet in response["Subnets"]:
            tags = {t["Key"]: t["Value"] for t in subnet.get("Tags", [])}
            resources.append(CloudResource(
                resource_type="aws_subnet",
                resource_id=subnet["SubnetId"],
                resource_arn=subnet.get("SubnetArn", f"arn:aws:ec2:{region}::subnet/{subnet['SubnetId']}"),
                resource_name=tags.get("Name", subnet["SubnetId"]),
                region=region,
                state_data={
                    "vpc_id": subnet.get("VpcId"),
                    "cidr_block": subnet.get("CidrBlock"),
                    "availability_zone": subnet.get("AvailabilityZone"),
                    "map_public_ip_on_launch": subnet.get("MapPublicIpOnLaunch"),
                },
                tags=tags,
            ))

        return resources

    def _fetch_security_group(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch security groups."""
        ec2 = self._get_client("ec2", region)
        resources = []

        response = ec2.describe_security_groups()
        for sg in response["SecurityGroups"]:
            tags = {t["Key"]: t["Value"] for t in sg.get("Tags", [])}
            resources.append(CloudResource(
                resource_type="aws_security_group",
                resource_id=sg["GroupId"],
                resource_arn=f"arn:aws:ec2:{region}::security-group/{sg['GroupId']}",
                resource_name=sg.get("GroupName", sg["GroupId"]),
                region=region,
                state_data={
                    "vpc_id": sg.get("VpcId"),
                    "description": sg.get("Description"),
                    "ingress_rules_count": len(sg.get("IpPermissions", [])),
                    "egress_rules_count": len(sg.get("IpPermissionsEgress", [])),
                },
                tags=tags,
            ))

        return resources

    def _fetch_eks(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch EKS clusters."""
        eks = self._get_client("eks", region)
        resources = []

        try:
            clusters = eks.list_clusters()["clusters"]
            for cluster_name in clusters:
                cluster = eks.describe_cluster(name=cluster_name)["cluster"]
                resources.append(CloudResource(
                    resource_type="aws_eks_cluster",
                    resource_id=cluster_name,
                    resource_arn=cluster.get("arn"),
                    resource_name=cluster_name,
                    region=region,
                    state_data={
                        "status": cluster.get("status"),
                        "version": cluster.get("version"),
                        "endpoint": cluster.get("endpoint"),
                        "vpc_id": cluster.get("resourcesVpcConfig", {}).get("vpcId"),
                    },
                    tags=cluster.get("tags", {}),
                ))
        except ClientError:
            pass

        return resources

    def _fetch_rds(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch RDS instances."""
        rds = self._get_client("rds", region)
        resources = []

        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for db in page["DBInstances"]:
                resources.append(CloudResource(
                    resource_type="aws_db_instance",
                    resource_id=db["DBInstanceIdentifier"],
                    resource_arn=db.get("DBInstanceArn"),
                    resource_name=db["DBInstanceIdentifier"],
                    region=region,
                    state_data={
                        "engine": db.get("Engine"),
                        "engine_version": db.get("EngineVersion"),
                        "instance_class": db.get("DBInstanceClass"),
                        "status": db.get("DBInstanceStatus"),
                        "multi_az": db.get("MultiAZ"),
                        "storage_type": db.get("StorageType"),
                    },
                    tags={t["Key"]: t["Value"] for t in db.get("TagList", [])},
                ))

        return resources

    def _fetch_s3(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch S3 buckets."""
        s3 = self._get_client("s3", region)
        resources = []

        try:
            buckets = s3.list_buckets()["Buckets"]
            for bucket in buckets:
                bucket_name = bucket["Name"]
                try:
                    # Get bucket location
                    location = s3.get_bucket_location(Bucket=bucket_name)
                    bucket_region = location.get("LocationConstraint") or "us-east-1"

                    # Only include if in requested region (or if fetching all)
                    if bucket_region == region or region == self.default_region:
                        resources.append(CloudResource(
                            resource_type="aws_s3_bucket",
                            resource_id=bucket_name,
                            resource_arn=f"arn:aws:s3:::{bucket_name}",
                            resource_name=bucket_name,
                            region=bucket_region,
                            state_data={
                                "creation_date": bucket.get("CreationDate").isoformat() if bucket.get("CreationDate") else None,
                            },
                            tags={},
                        ))
                except ClientError:
                    pass
        except ClientError:
            pass

        return resources

    def _fetch_lambda(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch Lambda functions."""
        lambda_client = self._get_client("lambda", region)
        resources = []

        paginator = lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            for func in page["Functions"]:
                resources.append(CloudResource(
                    resource_type="aws_lambda_function",
                    resource_id=func["FunctionName"],
                    resource_arn=func.get("FunctionArn"),
                    resource_name=func["FunctionName"],
                    region=region,
                    state_data={
                        "runtime": func.get("Runtime"),
                        "handler": func.get("Handler"),
                        "memory_size": func.get("MemorySize"),
                        "timeout": func.get("Timeout"),
                        "last_modified": func.get("LastModified"),
                    },
                    tags={},
                ))

        return resources

    def _fetch_alb(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch Application Load Balancers."""
        elbv2 = self._get_client("elbv2", region)
        resources = []

        paginator = elbv2.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for lb in page["LoadBalancers"]:
                if lb.get("Type") == "application":
                    resources.append(CloudResource(
                        resource_type="aws_lb",
                        resource_id=lb["LoadBalancerName"],
                        resource_arn=lb.get("LoadBalancerArn"),
                        resource_name=lb["LoadBalancerName"],
                        region=region,
                        state_data={
                            "type": lb.get("Type"),
                            "scheme": lb.get("Scheme"),
                            "state": lb.get("State", {}).get("Code"),
                            "dns_name": lb.get("DNSName"),
                            "vpc_id": lb.get("VpcId"),
                        },
                        tags={},
                    ))

        return resources

    def _fetch_dynamodb(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch DynamoDB tables."""
        dynamodb = self._get_client("dynamodb", region)
        resources = []

        paginator = dynamodb.get_paginator("list_tables")
        for page in paginator.paginate():
            for table_name in page["TableNames"]:
                try:
                    table = dynamodb.describe_table(TableName=table_name)["Table"]
                    resources.append(CloudResource(
                        resource_type="aws_dynamodb_table",
                        resource_id=table_name,
                        resource_arn=table.get("TableArn"),
                        resource_name=table_name,
                        region=region,
                        state_data={
                            "status": table.get("TableStatus"),
                            "item_count": table.get("ItemCount"),
                            "size_bytes": table.get("TableSizeBytes"),
                            "billing_mode": table.get("BillingModeSummary", {}).get("BillingMode"),
                        },
                        tags={},
                    ))
                except ClientError:
                    pass

        return resources

    def _fetch_iam_role(
        self,
        region: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[CloudResource]:
        """Fetch IAM roles (global service)."""
        iam = self._get_client("iam", region)
        resources = []

        paginator = iam.get_paginator("list_roles")
        for page in paginator.paginate():
            for role in page["Roles"]:
                resources.append(CloudResource(
                    resource_type="aws_iam_role",
                    resource_id=role["RoleName"],
                    resource_arn=role.get("Arn"),
                    resource_name=role["RoleName"],
                    region="global",
                    state_data={
                        "path": role.get("Path"),
                        "create_date": role.get("CreateDate").isoformat() if role.get("CreateDate") else None,
                        "description": role.get("Description"),
                    },
                    tags={},
                ))

        return resources
