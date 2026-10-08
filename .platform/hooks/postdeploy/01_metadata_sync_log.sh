#!/bin/bash
# Runs after EB configures (or stops) the CloudWatch agent. The log group must
# already exist with 30-day retention; the instance role cannot create it.
set -euo pipefail
env_name=$(/opt/elasticbeanstalk/bin/get-config container -k environment_name)
conf=/opt/aws/amazon-cloudwatch-agent/etc/brainscore-metadata-sync.json
cat > "$conf" <<JSON
{"logs": {"logs_collected": {"files": {"collect_list": [{
  "file_path": "/var/log/brainscore-metadata-sync.log",
  "log_group_name": "/aws/elasticbeanstalk/${env_name}/var/log/brainscore-metadata-sync.log",
  "log_stream_name": "{instance_id}"}]}}}}
JSON
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a append-config -m ec2 -s -c "file:$conf"
