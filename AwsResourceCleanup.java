import software.amazon.awssdk.auth.credentials.ProfileCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.ec2.Ec2Client;
import software.amazon.awssdk.services.ec2.model.*;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.*;
import software.amazon.awssdk.services.rds.RdsClient;
import software.amazon.awssdk.services.rds.model.*;
import software.amazon.awssdk.services.lambda.LambdaClient;
import software.amazon.awssdk.services.lambda.model.*;
import software.amazon.awssdk.services.elasticloadbalancing.ElasticLoadBalancingClient;
import software.amazon.awssdk.services.elasticloadbalancing.model.*;

import java.util.List;

public class AwsResourceCleanup {
    public static void main(String[] args) {
        Region region = Region.US_EAST_1; // Change this to your preferred region

        Ec2Client ec2 = Ec2Client.builder().region(region).credentialsProvider(ProfileCredentialsProvider.create()).build();
        S3Client s3 = S3Client.builder().region(region).credentialsProvider(ProfileCredentialsProvider.create()).build();
        RdsClient rds = RdsClient.builder().region(region).credentialsProvider(ProfileCredentialsProvider.create()).build();
        LambdaClient lambda = LambdaClient.builder().region(region).credentialsProvider(ProfileCredentialsProvider.create()).build();
        ElasticLoadBalancingClient elb = ElasticLoadBalancingClient.builder().region(region).credentialsProvider(ProfileCredentialsProvider.create()).build();

        deleteEC2Instances(ec2);
        deleteUnattachedVolumes(ec2);
        releaseElasticIps(ec2);
        deleteS3Buckets(s3);
        deleteRdsInstances(rds);
        deleteLambdaFunctions(lambda);
        deleteClassicLoadBalancers(elb);
        deleteVpcs(ec2);

        System.out.println("All major billable AWS resources have been deleted.");
    }

    static void deleteEC2Instances(Ec2Client ec2) {
        DescribeInstancesResponse response = ec2.describeInstances();
        for (Reservation r : response.reservations()) {
            for (Instance i : r.instances()) {
                ec2.terminateInstances(TerminateInstancesRequest.builder().instanceIds(i.instanceId()).build());
                System.out.println("Terminating instance: " + i.instanceId());
            }
        }
    }

    static void deleteUnattachedVolumes(Ec2Client ec2) {
        DescribeVolumesResponse response = ec2.describeVolumes(DescribeVolumesRequest.builder()
                .filters(Filter.builder().name("status").values("available").build()).build());
        for (Volume v : response.volumes()) {
            ec2.deleteVolume(DeleteVolumeRequest.builder().volumeId(v.volumeId()).build());
            System.out.println("Deleting volume: " + v.volumeId());
        }
    }

    static void releaseElasticIps(Ec2Client ec2) {
        DescribeAddressesResponse response = ec2.describeAddresses();
        for (Address a : response.addresses()) {
            if (a.allocationId() != null) {
                ec2.releaseAddress(ReleaseAddressRequest.builder().allocationId(a.allocationId()).build());
                System.out.println("Releasing EIP: " + a.allocationId());
            }
        }
    }

    static void deleteS3Buckets(S3Client s3) {
        ListBucketsResponse response = s3.listBuckets();
        for (Bucket b : response.buckets()) {
            ListObjectsV2Response objects = s3.listObjectsV2(ListObjectsV2Request.builder().bucket(b.name()).build());
            for (S3Object obj : objects.contents()) {
                s3.deleteObject(DeleteObjectRequest.builder().bucket(b.name()).key(obj.key()).build());
            }
            s3.deleteBucket(DeleteBucketRequest.builder().bucket(b.name()).build());
            System.out.println("Deleted S3 bucket: " + b.name());
        }
    }

    static void deleteRdsInstances(RdsClient rds) {
        DescribeDbInstancesResponse response = rds.describeDBInstances();
        for (DBInstance db : response.dbInstances()) {
            rds.deleteDBInstance(DeleteDbInstanceRequest.builder()
                    .dbInstanceIdentifier(db.dbInstanceIdentifier())
                    .skipFinalSnapshot(true)
                    .deleteAutomatedBackups(true)
                    .build());
            System.out.println("Deleted RDS instance: " + db.dbInstanceIdentifier());
        }
    }

    static void deleteLambdaFunctions(LambdaClient lambda) {
        ListFunctionsResponse response = lambda.listFunctions();
        for (FunctionConfiguration fn : response.functions()) {
            lambda.deleteFunction(DeleteFunctionRequest.builder().functionName(fn.functionName()).build());
            System.out.println("Deleted Lambda function: " + fn.functionName());
        }
    }

    static void deleteClassicLoadBalancers(ElasticLoadBalancingClient elb) {
        DescribeLoadBalancersResponse response = elb.describeLoadBalancers();
        for (LoadBalancerDescription lb : response.loadBalancerDescriptions()) {
            elb.deleteLoadBalancer(DeleteLoadBalancerRequest.builder().loadBalancerName(lb.loadBalancerName()).build());
            System.out.println("Deleted Load Balancer: " + lb.loadBalancerName());
        }
    }

    static void deleteVpcs(Ec2Client ec2) {
        DescribeVpcsResponse vpcs = ec2.describeVpcs();
        for (Vpc vpc : vpcs.vpcs()) {
            if (!vpc.isDefault()) {
                String vpcId = vpc.vpcId();

                // Subnets
                for (Subnet subnet : ec2.describeSubnets(DescribeSubnetsRequest.builder()
                        .filters(Filter.builder().name("vpc-id").values(vpcId).build()).build()).subnets()) {
                    ec2.deleteSubnet(DeleteSubnetRequest.builder().subnetId(subnet.subnetId()).build());
                }

                // Internet Gateways
                for (InternetGateway igw : ec2.describeInternetGateways(DescribeInternetGatewaysRequest.builder()
                        .filters(Filter.builder().name("attachment.vpc-id").values(vpcId).build()).build()).internetGateways()) {
                    ec2.detachInternetGateway(DetachInternetGatewayRequest.builder().internetGatewayId(igw.internetGatewayId()).vpcId(vpcId).build());
                    ec2.deleteInternetGateway(DeleteInternetGatewayRequest.builder().internetGatewayId(igw.internetGatewayId()).build());
                }

                // Route Tables (skip main)
                for (RouteTable rt : ec2.describeRouteTables(DescribeRouteTablesRequest.builder()
                        .filters(Filter.builder().name("vpc-id").values(vpcId).build()).build()).routeTables()) {
                    boolean isMain = rt.associations().stream().anyMatch(assoc -> assoc.main() != null && assoc.main());
                    if (!isMain) {
                        ec2.deleteRouteTable(DeleteRouteTableRequest.builder().routeTableId(rt.routeTableId()).build());
                    }
                }

                // Security Groups (skip default)
                for (SecurityGroup sg : ec2.describeSecurityGroups(DescribeSecurityGroupsRequest.builder()
                        .filters(Filter.builder().name("vpc-id").values(vpcId).build()).build()).securityGroups()) {
                    if (!sg.groupName().equals("default")) {
                        ec2.deleteSecurityGroup(DeleteSecurityGroupRequest.builder().groupId(sg.groupId()).build());
                    }
                }

                // Delete VPC
                ec2.deleteVpc(DeleteVpcRequest.builder().vpcId(vpcId).build());
                System.out.println("Deleted VPC: " + vpcId);
            }
        }
    }
}
