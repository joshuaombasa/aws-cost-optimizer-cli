import boto3
import logging
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def get_client(service_name):
    """Helper to create boto3 client."""
    return boto3.client(service_name)

def delete_ec2_instances():
    """Terminate all EC2 instances."""
    logging.info("🔄 Deleting EC2 instances...")
    ec2 = get_client('ec2')
    try:
        instances = ec2.describe_instances()
        instance_ids = [
            instance['InstanceId']
            for reservation in instances['Reservations']
            for instance in reservation['Instances']
        ]
        if instance_ids:
            ec2.terminate_instances(InstanceIds=instance_ids)
            logging.info(f"✅ Terminated EC2 instances: {instance_ids}")
        else:
            logging.info("ℹ️ No EC2 instances found.")
    except ClientError as e:
        logging.error(f"❌ Error deleting EC2 instances: {e}")

def delete_unattached_volumes():
    """Delete all unattached EBS volumes."""
    logging.info("🔄 Deleting unattached EBS volumes...")
    ec2 = get_client('ec2')
    try:
        volumes = ec2.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])
        for volume in volumes['Volumes']:
            ec2.delete_volume(VolumeId=volume['VolumeId'])
            logging.info(f"✅ Deleted volume: {volume['VolumeId']}")
    except ClientError as e:
        logging.error(f"❌ Error deleting volumes: {e}")

def release_elastic_ips():
    """Release all Elastic IPs."""
    logging.info("🔄 Releasing Elastic IPs...")
    ec2 = get_client('ec2')
    try:
        addresses = ec2.describe_addresses()
        for address in addresses['Addresses']:
            if 'AllocationId' in address:
                ec2.release_address(AllocationId=address['AllocationId'])
                logging.info(f"✅ Released EIP: {address['AllocationId']}")
    except ClientError as e:
        logging.error(f"❌ Error releasing Elastic IPs: {e}")

def delete_s3_buckets():
    """Delete all S3 buckets and their contents."""
    logging.info("🔄 Deleting S3 buckets...")
    s3 = boto3.resource('s3')
    try:
        for bucket in s3.buckets.all():
            logging.info(f"🗑️ Deleting contents of bucket: {bucket.name}")
            bucket.objects.all().delete()
            bucket.delete()
            logging.info(f"✅ Deleted bucket: {bucket.name}")
    except ClientError as e:
        logging.error(f"❌ Error deleting S3 buckets: {e}")

def delete_rds_instances():
    """Delete all RDS instances."""
    logging.info("🔄 Deleting RDS instances...")
    rds = get_client('rds')
    try:
        instances = rds.describe_db_instances()
        for db in instances['DBInstances']:
            db_id = db['DBInstanceIdentifier']
            rds.delete_db_instance(
                DBInstanceIdentifier=db_id,
                SkipFinalSnapshot=True,
                DeleteAutomatedBackups=True
            )
            logging.info(f"✅ Deleted RDS instance: {db_id}")
    except ClientError as e:
        logging.error(f"❌ Error deleting RDS instances: {e}")

def delete_lambda_functions():
    """Delete all Lambda functions."""
    logging.info("🔄 Deleting Lambda functions...")
    lamb = get_client('lambda')
    try:
        paginator = lamb.get_paginator('list_functions')
        for page in paginator.paginate():
            for fn in page['Functions']:
                lamb.delete_function(FunctionName=fn['FunctionName'])
                logging.info(f"✅ Deleted Lambda function: {fn['FunctionName']}")
    except ClientError as e:
        logging.error(f"❌ Error deleting Lambda functions: {e}")

def delete_elbs():
    """Delete all Classic Load Balancers."""
    logging.info("🔄 Deleting Classic Load Balancers...")
    elb = get_client('elb')
    try:
        lbs = elb.describe_load_balancers()
        for lb in lbs['LoadBalancerDescriptions']:
            elb.delete_load_balancer(LoadBalancerName=lb['LoadBalancerName'])
            logging.info(f"✅ Deleted Load Balancer: {lb['LoadBalancerName']}")
    except ClientError as e:
        logging.error(f"❌ Error deleting ELBs: {e}")

def delete_vpcs():
    """Delete all non-default VPCs along with their dependencies."""
    logging.info("🔄 Deleting non-default VPCs...")
    ec2 = get_client('ec2')
    try:
        vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['false']}])['Vpcs']
        for vpc in vpcs:
            vpc_id = vpc['VpcId']
            logging.info(f"🧹 Cleaning VPC: {vpc_id}")

            # Delete subnets
            subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']
            for subnet in subnets:
                ec2.delete_subnet(SubnetId=subnet['SubnetId'])

            # Delete Internet Gateways
            igws = ec2.describe_internet_gateways(Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}])['InternetGateways']
            for igw in igws:
                ec2.detach_internet_gateway(InternetGatewayId=igw['InternetGatewayId'], VpcId=vpc_id)
                ec2.delete_internet_gateway(InternetGatewayId=igw['InternetGatewayId'])

            # Delete non-main route tables
            rts = ec2.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['RouteTables']
            for rt in rts:
                if not any(assoc.get('Main', False) for assoc in rt['Associations']):
                    ec2.delete_route_table(RouteTableId=rt['RouteTableId'])

            # Delete non-default security groups
            sgs = ec2.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['SecurityGroups']
            for sg in sgs:
                if sg['GroupName'] != 'default':
                    ec2.delete_security_group(GroupId=sg['GroupId'])

            # Delete the VPC
            ec2.delete_vpc(VpcId=vpc_id)
            logging.info(f"✅ Deleted VPC: {vpc_id}")
    except ClientError as e:
        logging.error(f"❌ Error deleting VPCs: {e}")

def main():
    logging.info("🚀 Starting AWS resource cleanup...")
    delete_ec2_instances()
    delete_unattached_volumes()
    release_elastic_ips()
    delete_s3_buckets()
    delete_rds_instances()
    delete_lambda_functions()
    delete_elbs()
    delete_vpcs()
    logging.info("✅ Cleanup completed successfully.")

if __name__ == "__main__":
    main()
