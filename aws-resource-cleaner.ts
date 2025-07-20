import {
  EC2Client,
  DescribeInstancesCommand,
  TerminateInstancesCommand,
  DescribeVolumesCommand,
  DeleteVolumeCommand,
  DescribeAddressesCommand,
  ReleaseAddressCommand,
  DescribeVpcsCommand,
  DescribeSubnetsCommand,
  DeleteSubnetCommand,
  DescribeInternetGatewaysCommand,
  DetachInternetGatewayCommand,
  DeleteInternetGatewayCommand,
  DescribeRouteTablesCommand,
  DeleteRouteTableCommand,
  DescribeSecurityGroupsCommand,
  DeleteSecurityGroupCommand,
  DeleteVpcCommand
} from "@aws-sdk/client-ec2";

import {
  S3Client,
  ListBucketsCommand,
  DeleteBucketCommand,
  ListObjectsV2Command,
  DeleteObjectsCommand
} from "@aws-sdk/client-s3";

import {
  RDSClient,
  DescribeDBInstancesCommand,
  DeleteDBInstanceCommand
} from "@aws-sdk/client-rds";

import {
  LambdaClient,
  ListFunctionsCommand,
  DeleteFunctionCommand
} from "@aws-sdk/client-lambda";

import {
  ElasticLoadBalancingClient,
  DescribeLoadBalancersCommand,
  DeleteLoadBalancerCommand
} from "@aws-sdk/client-elastic-load-balancing";

const ec2 = new EC2Client({});
const s3 = new S3Client({});
const rds = new RDSClient({});
const lambda = new LambdaClient({});
const elb = new ElasticLoadBalancingClient({});

const log = console.log;

async function deleteEC2Instances() {
  log("Deleting EC2 instances...");
  const result = await ec2.send(new DescribeInstancesCommand({}));
  const instanceIds: string[] = [];

  result.Reservations?.forEach(res =>
    res.Instances?.forEach(inst => {
      if (inst.InstanceId) instanceIds.push(inst.InstanceId);
    })
  );

  if (instanceIds.length) {
    await ec2.send(new TerminateInstancesCommand({ InstanceIds: instanceIds }));
    log(`Terminated EC2 instances: ${instanceIds}`);
  } else {
    log("No EC2 instances found.");
  }
}

async function deleteUnattachedVolumes() {
  log("Deleting unattached EBS volumes...");
  const result = await ec2.send(new DescribeVolumesCommand({
    Filters: [{ Name: "status", Values: ["available"] }]
  }));
  for (const vol of result.Volumes || []) {
    if (vol.VolumeId) {
      await ec2.send(new DeleteVolumeCommand({ VolumeId: vol.VolumeId }));
      log(`Deleted volume: ${vol.VolumeId}`);
    }
  }
}

async function releaseElasticIPs() {
  log("Releasing Elastic IPs...");
  const result = await ec2.send(new DescribeAddressesCommand({}));
  for (const address of result.Addresses || []) {
    if (address.AllocationId) {
      await ec2.send(new ReleaseAddressCommand({ AllocationId: address.AllocationId }));
      log(`Released EIP: ${address.AllocationId}`);
    }
  }
}

async function deleteS3Buckets() {
  log("Deleting S3 buckets...");
  const result = await s3.send(new ListBucketsCommand({}));
  for (const bucket of result.Buckets || []) {
    const bucketName = bucket.Name!;
    log(`Deleting contents of bucket: ${bucketName}`);

    const objects = await s3.send(new ListObjectsV2Command({ Bucket: bucketName }));
    if (objects.Contents?.length) {
      await s3.send(new DeleteObjectsCommand({
        Bucket: bucketName,
        Delete: {
          Objects: objects.Contents.map(obj => ({ Key: obj.Key! })),
          Quiet: true
        }
      }));
    }

    await s3.send(new DeleteBucketCommand({ Bucket: bucketName }));
    log(`Deleted bucket: ${bucketName}`);
  }
}

async function deleteRDSInstances() {
  log("Deleting RDS instances...");
  const result = await rds.send(new DescribeDBInstancesCommand({}));
  for (const db of result.DBInstances || []) {
    if (db.DBInstanceIdentifier) {
      await rds.send(new DeleteDBInstanceCommand({
        DBInstanceIdentifier: db.DBInstanceIdentifier,
        SkipFinalSnapshot: true,
        DeleteAutomatedBackups: true
      }));
      log(`Deleted RDS instance: ${db.DBInstanceIdentifier}`);
    }
  }
}

async function deleteLambdaFunctions() {
  log("Deleting Lambda functions...");
  const result = await lambda.send(new ListFunctionsCommand({}));
  for (const fn of result.Functions || []) {
    await lambda.send(new DeleteFunctionCommand({ FunctionName: fn.FunctionName! }));
    log(`Deleted Lambda function: ${fn.FunctionName}`);
  }
}

async function deleteELBs() {
  log("Deleting Classic Load Balancers...");
  const result = await elb.send(new DescribeLoadBalancersCommand({}));
  for (const lb of result.LoadBalancerDescriptions || []) {
    await elb.send(new DeleteLoadBalancerCommand({ LoadBalancerName: lb.LoadBalancerName! }));
    log(`Deleted Load Balancer: ${lb.LoadBalancerName}`);
  }
}

async function deleteVPCs() {
  log("Deleting non-default VPCs...");
  const vpcs = await ec2.send(new DescribeVpcsCommand({
    Filters: [{ Name: "isDefault", Values: ["false"] }]
  }));

  for (const vpc of vpcs.Vpcs || []) {
    const vpcId = vpc.VpcId!;
    log(`Cleaning VPC: ${vpcId}`);

    const subnets = await ec2.send(new DescribeSubnetsCommand({
      Filters: [{ Name: "vpc-id", Values: [vpcId] }]
    }));
    for (const subnet of subnets.Subnets || []) {
      await ec2.send(new DeleteSubnetCommand({ SubnetId: subnet.SubnetId! }));
    }

    const igws = await ec2.send(new DescribeInternetGatewaysCommand({
      Filters: [{ Name: "attachment.vpc-id", Values: [vpcId] }]
    }));
    for (const igw of igws.InternetGateways || []) {
      await ec2.send(new DetachInternetGatewayCommand({ InternetGatewayId: igw.InternetGatewayId!, VpcId: vpcId }));
      await ec2.send(new DeleteInternetGatewayCommand({ InternetGatewayId: igw.InternetGatewayId! }));
    }

    const routeTables = await ec2.send(new DescribeRouteTablesCommand({
      Filters: [{ Name: "vpc-id", Values: [vpcId] }]
    }));
    for (const rt of routeTables.RouteTables || []) {
      const isMain = rt.Associations?.some(a => a.Main);
      if (!isMain) {
        await ec2.send(new DeleteRouteTableCommand({ RouteTableId: rt.RouteTableId! }));
      }
    }

    const sgs = await ec2.send(new DescribeSecurityGroupsCommand({
      Filters: [{ Name: "vpc-id", Values: [vpcId] }]
    }));
    for (const sg of sgs.SecurityGroups || []) {
      if (sg.GroupName !== "default") {
        await ec2.send(new DeleteSecurityGroupCommand({ GroupId: sg.GroupId! }));
      }
    }

    await ec2.send(new DeleteVpcCommand({ VpcId: vpcId }));
    log(`Deleted VPC: ${vpcId}`);
  }
}

async function main() {
  log("Starting AWS resource cleanup...");
  await deleteEC2Instances();
  await deleteUnattachedVolumes();
  await releaseElasticIPs();
  await deleteS3Buckets();
  await deleteRDSInstances();
  await deleteLambdaFunctions();
  await deleteELBs();
  await deleteVPCs();
  log("Cleanup completed successfully.");
}

main().catch(err => console.error("Error:", err));
