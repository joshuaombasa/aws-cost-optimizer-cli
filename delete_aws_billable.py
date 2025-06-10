import boto3
import logging
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def delete_ec2_instances():
    logging.info("Deleting EC2 instances...")
    ec2 = boto3.client('ec2')
    try:
        instances = ec2.describe_instances()
        instance_ids = [
            instance['InstanceId']
            for r in instances['Reservations']
            for instance in r['Instances']
        ]
        if instance_ids:
            ec2.terminate_instances(InstanceIds=instance_ids)
            logging.info(f"Terminated instances: {instance_ids}")
        else:
            logging.info("No EC2 instances to delete.")
    except ClientError as e:
        logging.error(f"Failed to delete EC2 instances: {e}")

def delete_unattached_volumes():
    logging.info("Deleting unattached EBS volumes...")
    ec2 = boto3.client('ec2')
    try:
        volumes = ec2.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])
        for volume in volumes['Volumes']:
            ec2.delete_volume(VolumeId=volume['VolumeId'])
            logging.info(f"Deleted volume: {volume['VolumeId']}")
    except ClientError as e:
        logging.error(f"Failed to delete EBS volumes: {e}")

def release_elastic_ips():
    logging.info("Releasing Elastic IPs...")
    ec2 = boto3.client('ec2')
    try:
        addresses = ec2.describe_addresses()
        for address in addresses['Addresses']:
            if 'AllocationId' in address:
                ec2.release_address(AllocationId=address['AllocationId'])
                logging.info(f"Released EIP: {address['AllocationId']}")
    except ClientError as e:
        logging.error(f"Failed to release Elastic IPs: {e}")

def delete_s3_buckets():
    logging.info("Deleting S3 buckets...")
    s3 = boto3.resource('s3')
    try:
        for bucket in s3.buckets.all():
            logging.info(f"Deleting contents of bucket: {bucket.name}")
            bucket.objects.all().delete()
            bucket.delete()
            logging.info(f"Deleted bucket: {bucket.name}")
    except ClientError as e:
        logging.error(f"Failed to delete S3 buckets: {e}")

def delete_rds_instances():
    logging.info("Deleting RDS instances...")
    rds = boto3.client('rds')
    try:
        dbs = rds.describe_db_instances()
        for db in dbs['DBInstances']:
            db_id = db['DBInstanceIdentifier']
            rds.delete_db_instance(
                DBInstanceIdentifier=db_id,
                SkipFinalSnapshot=True,
                DeleteAutomatedBackups=True
            )
            logging.info(f"Deleted RDS instance: {db_id}")
    except ClientError as e:
        logging.error(f"Failed to delete RDS instances: {e}")

def delete_lambda_functions():
    logging.info("Deleting Lambda functions...")
    lamb = boto3.client('lambda')
    try:
        paginator = lamb.get_paginator('list_functions')
        for page in paginator.paginate():
            for fn in page['Functions']:
                lamb.delete_function(FunctionName=fn['FunctionName'])
                logging.info(f"Deleted Lambda function: {fn['FunctionName']}")
    except ClientError as e:
        logging.error(f"Failed to delete Lambda functions: {e}")

def delete_elbs():
    logging.info("Deleting Classic Load Balancers...")
    elb = boto3.client('elb')
    try:
        lbs = elb.describe_load_balancers()
        for lb in lbs['LoadBalancerDescriptions']:
            elb.delete_load_balancer(LoadBalancerName=lb['LoadBalancerName'])
            logging.info(f"Deleted Load Balancer: {lb['LoadBalancerName']}")
    except ClientError as e:
        logging.error(f"Failed to delete ELBs: {e}")

def delete_vpcs():
    logging.info("Deleting non-default VPCs...")
    ec2 = boto3.client('ec2')
    try:
        vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['false']}])['Vpcs']
        for vpc in vpcs:
            vpc_id = vpc['VpcId']
            logging.info(f"Deleting resources in VPC {vpc_id}")

            # Subnets
            subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']
            for subnet in subnets:
                ec2.delete_subnet(SubnetId=subnet['SubnetId'])

            # Internet Gateways
            igws = ec2.describe_internet_gateways(Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}])['InternetGateways']
            for igw in igws:
                ec2.detach_internet_gateway(InternetGatewayId=igw['InternetGatewayId'], VpcId=vpc_id)
                ec2.delete_internet_gateway(InternetGatewayId=igw['InternetGatewayId'])

            # Route Tables
            rts = ec2.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['RouteTables']
            for rt in rts:
                if not any(assoc.get('Main', False) for assoc in rt['Associations']):
                    ec2.delete_route_table(RouteTableId=rt['RouteTableId'])

            # Security Groups
            sgs = ec2.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['SecurityGroups']
            for sg in sgs:
                if sg['GroupName'] != 'default':
                    ec2.delete_security_group(GroupId=sg['GroupId'])

            # Finally, delete the VPC
            ec2.delete_vpc(VpcId=vpc_id)
            logging.info(f"Deleted VPC: {vpc_id}")
    except ClientError as e:
        logging.error(f"Failed to delete VPCs: {e}")

def main():
    logging.info("Starting AWS resource cleanup...")
    delete_ec2_instances()
    delete_unattached_volumes()
    release_elastic_ips()
    delete_s3_buckets()
    delete_rds_instances()
    delete_lambda_functions()
    delete_elbs()
    delete_vpcs()
    logging.info("✅ Cleanup completed. All major AWS resources have been deleted.")

if __name__ == "__main__":
    main()
