#!/bin/bash
set -e

echo "Deleting EC2 instances..."
instance_ids=$(aws ec2 describe-instances --query 'Reservations[*].Instances[*].InstanceId' --output text)
if [ -n "$instance_ids" ]; then
    aws ec2 terminate-instances --instance-ids $instance_ids
fi

echo "Deleting unattached EBS volumes..."
volume_ids=$(aws ec2 describe-volumes --filters Name=status,Values=available --query "Volumes[*].VolumeId" --output text)
if [ -n "$volume_ids" ]; then
    aws ec2 delete-volume --volume-id $volume_ids
fi

echo "Releasing Elastic IPs..."
allocation_ids=$(aws ec2 describe-addresses --query 'Addresses[*].AllocationId' --output text)
for id in $allocation_ids; do
    aws ec2 release-address --allocation-id $id
done

echo "Deleting S3 buckets..."
buckets=$(aws s3api list-buckets --query 'Buckets[*].Name' --output text)
for bucket in $buckets; do
    aws s3 rb s3://$bucket --force
done

echo "Deleting RDS instances..."
dbs=$(aws rds describe-db-instances --query 'DBInstances[*].DBInstanceIdentifier' --output text)
for db in $dbs; do
    aws rds delete-db-instance --db-instance-identifier $db --skip-final-snapshot --delete-automated-backups
done

echo "Deleting Lambda functions..."
functions=$(aws lambda list-functions --query 'Functions[*].FunctionName' --output text)
for fn in $functions; do
    aws lambda delete-function --function-name $fn
done

echo "Deleting Load Balancers..."
lbs=$(aws elb describe-load-balancers --query 'LoadBalancerDescriptions[*].LoadBalancerName' --output text)
for lb in $lbs; do
    aws elb delete-load-balancer --load-balancer-name $lb
done

echo "Deleting VPCs (except default)..."
vpcs=$(aws ec2 describe-vpcs --query "Vpcs[?IsDefault==\`false\`].VpcId" --output text)
for vpc in $vpcs; do
    echo "Deleting resources in VPC $vpc"
    # Subnets
    subnets=$(aws ec2 describe-subnets --filters Name=vpc-id,Values=$vpc --query 'Subnets[*].SubnetId' --output text)
    for subnet in $subnets; do
        aws ec2 delete-subnet --subnet-id $subnet
    done
    # Internet Gateways
    igws=$(aws ec2 describe-internet-gateways --filters Name=attachment.vpc-id,Values=$vpc --query 'InternetGateways[*].InternetGatewayId' --output text)
    for igw in $igws; do
        aws ec2 detach-internet-gateway --internet-gateway-id $igw --vpc-id $vpc
        aws ec2 delete-internet-gateway --internet-gateway-id $igw
    done
    # Route tables (skip main)
    rts=$(aws ec2 describe-route-tables --filters Name=vpc-id,Values=$vpc --query 'RouteTables[?Associations[?Main==`false`]].RouteTableId' --output text)
    for rt in $rts; do
        aws ec2 delete-route-table --route-table-id $rt
    done
    # Security groups (skip default)
    sgs=$(aws ec2 describe-security-groups --filters Name=vpc-id,Values=$vpc --query 'SecurityGroups[?GroupName!=`default`].GroupId' --output text)
    for sg in $sgs; do
        aws ec2 delete-security-group --group-id $sg
    done
    # Finally delete the VPC
    aws ec2 delete-vpc --vpc-id $vpc
done

echo "✅ All major billable AWS resources have been deleted."
