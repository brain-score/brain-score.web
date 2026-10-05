"""Best-effort health metrics without contributor identities or credentials."""
import logging

import boto3
from botocore.config import Config
from django.conf import settings

NAMESPACE = "BrainScore/MetadataSynchronization"
logger = logging.getLogger(__name__)


def report_run(success):
    if not getattr(settings, "MODEL_METADATA_SYNC_METRICS_ENABLED", False):
        return
    try:
        environment = getattr(settings, "MODEL_METADATA_SYNC_METRICS_ENVIRONMENT", "")
        region = getattr(settings, "MODEL_METADATA_SYNC_METRICS_REGION", "")
        if not environment or not region:
            raise ValueError("Explicit metric environment and region are required")
        client = boto3.client("cloudwatch", region_name=region,
                              config=Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 0}))
        client.put_metric_data(Namespace=NAMESPACE, MetricData=[{
            "MetricName": "RunSuccessful",
            "Dimensions": [{"Name": "Environment", "Value": environment}],
            "Value": 1 if success else 0,
            "Unit": "Count",
        }])
    except Exception as exc:
        # Failure to report must not undo publication or mask its original error.
        logger.warning("Metadata health metric unavailable: %s", type(exc).__name__)
