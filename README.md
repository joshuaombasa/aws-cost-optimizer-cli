# AWS Cost Killer

This script uses AWS CLI to automatically delete all major billable resources in your AWS account, including:

- EC2 instances and unattached volumes
- Elastic IPs
- S3 buckets
- RDS databases
- Lambda functions
- Load balancers
- Non-default VPCs and associated resources

> ⚠️ **Warning:** This will **permanently delete** resources. Use at your own risk.

## Usage

1. Configure AWS CLI:

```bash
aws configure
