package main

import (
    "context"
    "fmt"
    "log"

    "github.com/aws/aws-sdk-go-v2/aws"
    "github.com/aws/aws-sdk-go-v2/config"
    "github.com/aws/aws-sdk-go-v2/service/ec2"
    ec2types "github.com/aws/aws-sdk-go-v2/service/ec2/types"
    "github.com/aws/aws-sdk-go-v2/service/s3"
    "github.com/aws/aws-sdk-go-v2/service/rds"
    "github.com/aws/aws-sdk-go-v2/service/lambda"
    "github.com/aws/aws-sdk-go-v2/service/elasticloadbalancing"
)

var ctx = context.TODO()

func getConfig() aws.Config {
    cfg, err := config.LoadDefaultConfig(ctx)
    if err != nil {
        log.Fatalf("Error loading AWS config: %v", err)
    }
    return cfg
}

func deleteEC2Instances(cfg aws.Config) {
    client := ec2.NewFromConfig(cfg)
    log.Println("Deleting EC2 instances...")

    output, err := client.DescribeInstances(ctx, &ec2.DescribeInstancesInput{})
    if err != nil {
        log.Printf("Error describing instances: %v\n", err)
        return
    }

    var instanceIds []string
    for _, reservation := range output.Reservations {
        for _, instance := range reservation.Instances {
            instanceIds = append(instanceIds, *instance.InstanceId)
        }
    }

    if len(instanceIds) > 0 {
        _, err := client.TerminateInstances(ctx, &ec2.TerminateInstancesInput{
            InstanceIds: instanceIds,
        })
        if err != nil {
            log.Printf("Error terminating instances: %v\n", err)
        } else {
            log.Printf("Terminated EC2 instances: %v\n", instanceIds)
        }
    } else {
        log.Println("No EC2 instances found.")
    }
}

func deleteUnattachedVolumes(cfg aws.Config) {
    client := ec2.NewFromConfig(cfg)
    log.Println("Deleting unattached EBS volumes...")

    output, err := client.DescribeVolumes(ctx, &ec2.DescribeVolumesInput{
        Filters: []ec2types.Filter{{Name: aws.String("status"), Values: []string{"available"}}},
    })
    if err != nil {
        log.Printf("Error describing volumes: %v\n", err)
        return
    }

    for _, volume := range output.Volumes {
        _, err := client.DeleteVolume(ctx, &ec2.DeleteVolumeInput{VolumeId: volume.VolumeId})
        if err != nil {
            log.Printf("Error deleting volume %s: %v\n", *volume.VolumeId, err)
        } else {
            log.Printf("Deleted volume: %s\n", *volume.VolumeId)
        }
    }
}

func releaseElasticIPs(cfg aws.Config) {
    client := ec2.NewFromConfig(cfg)
    log.Println("Releasing Elastic IPs...")

    output, err := client.DescribeAddresses(ctx, &ec2.DescribeAddressesInput{})
    if err != nil {
        log.Printf("Error describing addresses: %v\n", err)
        return
    }

    for _, addr := range output.Addresses {
        if addr.AllocationId != nil {
            _, err := client.ReleaseAddress(ctx, &ec2.ReleaseAddressInput{
                AllocationId: addr.AllocationId,
            })
            if err != nil {
                log.Printf("Error releasing EIP %s: %v\n", *addr.AllocationId, err)
            } else {
                log.Printf("Released EIP: %s\n", *addr.AllocationId)
            }
        }
    }
}

func deleteS3Buckets(cfg aws.Config) {
    client := s3.NewFromConfig(cfg)
    log.Println("Deleting S3 buckets...")

    output, err := client.ListBuckets(ctx, &s3.ListBucketsInput{})
    if err != nil {
        log.Printf("Error listing buckets: %v\n", err)
        return
    }

    for _, bucket := range output.Buckets {
        name := *bucket.Name
        log.Printf("Deleting contents of bucket: %s\n", name)

        listObjects, _ := client.ListObjectsV2(ctx, &s3.ListObjectsV2Input{
            Bucket: &name,
        })

        for _, obj := range listObjects.Contents {
            _, _ = client.DeleteObject(ctx, &s3.DeleteObjectInput{
                Bucket: &name,
                Key:    obj.Key,
            })
        }

        _, err = client.DeleteBucket(ctx, &s3.DeleteBucketInput{
            Bucket: &name,
        })

        if err != nil {
            log.Printf("Error deleting bucket %s: %v\n", name, err)
        } else {
            log.Printf("Deleted bucket: %s\n", name)
        }
    }
}

func deleteRDSInstances(cfg aws.Config) {
    client := rds.NewFromConfig(cfg)
    log.Println("Deleting RDS instances...")

    output, err := client.DescribeDBInstances(ctx, &rds.DescribeDBInstancesInput{})
    if err != nil {
        log.Printf("Error describing RDS instances: %v\n", err)
        return
    }

    for _, db := range output.DBInstances {
        id := *db.DBInstanceIdentifier
        _, err := client.DeleteDBInstance(ctx, &rds.DeleteDBInstanceInput{
            DBInstanceIdentifier: aws.String(id),
            SkipFinalSnapshot:    true,
            DeleteAutomatedBackups: true,
        })
        if err != nil {
            log.Printf("Error deleting RDS instance %s: %v\n", id, err)
        } else {
            log.Printf("Deleted RDS instance: %s\n", id)
        }
    }
}

func deleteLambdaFunctions(cfg aws.Config) {
    client := lambda.NewFromConfig(cfg)
    log.Println("Deleting Lambda functions...")

    output, err := client.ListFunctions(ctx, &lambda.ListFunctionsInput{})
    if err != nil {
        log.Printf("Error listing Lambda functions: %v\n", err)
        return
    }

    for _, fn := range output.Functions {
        _, err := client.DeleteFunction(ctx, &lambda.DeleteFunctionInput{
            FunctionName: fn.FunctionName,
        })
        if err != nil {
            log.Printf("Error deleting Lambda function %s: %v\n", *fn.FunctionName, err)
        } else {
            log.Printf("Deleted Lambda function: %s\n", *fn.FunctionName)
        }
    }
}

func deleteELBs(cfg aws.Config) {
    client := elasticloadbalancing.NewFromConfig(cfg)
    log.Println("Deleting Classic Load Balancers...")

    output, err := client.DescribeLoadBalancers(ctx, &elasticloadbalancing.DescribeLoadBalancersInput{})
    if err != nil {
        log.Printf("Error describing ELBs: %v\n", err)
        return
    }

    for _, lb := range output.LoadBalancerDescriptions {
        _, err := client.DeleteLoadBalancer(ctx, &elasticloadbalancing.DeleteLoadBalancerInput{
            LoadBalancerName: lb.LoadBalancerName,
        })
        if err != nil {
            log.Printf("Error deleting ELB %s: %v\n", *lb.LoadBalancerName, err)
        } else {
            log.Printf("Deleted ELB: %s\n", *lb.LoadBalancerName)
        }
    }
}

func main() {
    log.Println("Starting AWS resource cleanup...")
    cfg := getConfig()

    deleteEC2Instances(cfg)
    deleteUnattachedVolumes(cfg)
    releaseElasticIPs(cfg)
    deleteS3Buckets(cfg)
    deleteRDSInstances(cfg)
    deleteLambdaFunctions(cfg)
    deleteELBs(cfg)

    log.Println("Cleanup completed.")
}
