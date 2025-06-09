import boto3

def delete_ec2_instances():
    print("Deleting EC2 instances...")
    ec2 = boto3.client('ec2')
    instances = ec2.describe_instances()
    instance_ids = [
        instance['InstanceId']
        for r in instances['Reservations']
        for instance in r['Instances']
    ]
    if instance_ids:
        ec2.terminate_instances(InstanceIds=instance_ids)

def delete_unattached_volumes():
    print("Deleting unattached EBS volumes...")
    ec2 = boto3.client('ec2')
    volumes = ec2.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])
    for volume in volumes['Volumes']:
        ec2.delete_volume(VolumeId=volume['VolumeId'])

def release_elastic_ips():
    print("Releasing Elastic IPs...")
    ec2 = boto3.client('ec2')
    addresses = ec2.describe_addresses()
    for address in addresses['Addresses']:
        if 'AllocationId' in address:
            ec2.release_address(AllocationId=address['AllocationId'])

def delete_s3_buckets():
    print("Deleting S3 buckets...")
    s3 = boto3.resource('s3')
    for bucket in s3.buckets.all():
        print(f"Deleting contents of bucket: {bucket.name}")
        bucket.objects.all().delete()
        print(f"Deleting bucket: {bucket.name}")
        bucket.delete()

def delete_rds_instances():
    print("Deleting RDS instances...")
    rds = boto3.client('rds')
    dbs = rds.describe_db_instances()
    for db in dbs['DBInstances']:
        rds.delete_db_instance(
            DBInstanceIdentifier=db['DBInstanceIdentifier'],
            SkipFinalSnapshot=True,
            DeleteAutomatedBackups=True
        )

def delete_lambda_functions():
    print("Deleting Lambda functions...")
    lamb = boto3.client('lambda')
    functions = lamb.list_functions()
    for fn in functions['Functions']:
        lamb.delete_function(FunctionName=fn['FunctionName'])

def delete_elbs():
    print("Deleting Load Balancers...")
    elb = boto3.client('elb')
    lbs = elb.describe_load_balancers()
    for lb in lbs['LoadBalancerDescriptions']:
        elb.delete_load_balancer(LoadBalancerName=lb['LoadBalancerName'])

def delete_vpcs():
    print("Deleting VPCs (except default)...")
    ec2 = boto3.client('ec2')
    vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['false']}])['Vpcs']
    
    for vpc in vpcs:
        vpc_id = vpc['VpcId']
        print(f"Deleting resources in VPC {vpc_id}")
        
        # Delete subnets
        subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']
        for subnet in subnets:
            ec2.delete_subnet(SubnetId=subnet['SubnetId'])

        # Detach & delete Internet Gateways
        igws = ec2.describe_internet_gateways(Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}])['InternetGateways']
        for igw in igws:
            ec2.detach_internet_gateway(InternetGatewayId=igw['InternetGatewayId'], VpcId=vpc_id)
            ec2.delete_internet_gateway(InternetGatewayId=igw['InternetGatewayId'])

        # Delete non-main Route Tables
        rts = ec2.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['RouteTables']
        for rt in rts:
            if not any(assoc.get('Main', False) for assoc in rt['Associations']):
                ec2.delete_route_table(RouteTableId=rt['RouteTableId'])

        # Delete non-default Security Groups
        sgs = ec2.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['SecurityGroups']
        for sg in sgs:
            if sg['GroupName'] != 'default':
                ec2.delete_security_group(GroupId=sg['GroupId'])

        # Delete the VPC
        ec2.delete_vpc(VpcId=vpc_id)

def main():
    delete_ec2_instances()
    delete_unattached_volumes()
    release_elastic_ips()
    delete_s3_buckets()
    delete_rds_instances()
    delete_lambda_functions()
    delete_elbs()
    delete_vpcs()
    print("✅ All major billable AWS resources have been deleted.")

if __name__ == "__main__":
    main()
