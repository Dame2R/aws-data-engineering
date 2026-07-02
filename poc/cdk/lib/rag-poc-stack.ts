import * as cdk from 'aws-cdk-lib';
import { Duration, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as rds from 'aws-cdk-lib/aws-rds';
import { Construct } from 'constructs';

const DATABASE_NAME = 'ragdemo';

export class RagPocStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const vpc = new ec2.Vpc(this, 'RagPocVpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        {
          name: 'Database',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        },
      ],
    });

    const bedrockRole = new iam.Role(this, 'AuroraBedrockRole', {
      assumedBy: new iam.ServicePrincipal('rds.amazonaws.com'),
      description: 'Optional role for Aurora PostgreSQL aws_ml SQL functions that call Amazon Bedrock.',
    });

    bedrockRole.addToPolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel'],
      resources: [
        Stack.of(this).formatArn({
          service: 'bedrock',
          resource: 'foundation-model',
          resourceName: '*',
          arnFormat: cdk.ArnFormat.SLASH_RESOURCE_NAME,
          account: '',
        }),
        Stack.of(this).formatArn({
          service: 'bedrock',
          resource: 'inference-profile',
          resourceName: '*',
          arnFormat: cdk.ArnFormat.SLASH_RESOURCE_NAME,
        }),
      ],
    }));

    const cluster = new rds.DatabaseCluster(this, 'RagPocCluster', {
      // Aurora PostgreSQL 16 supports pgvector for RAG. Aurora PG 16, 17, and 18 currently ship pgvector 0.8.x in recent releases.
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_16_6,
      }),
      writer: rds.ClusterInstance.serverlessV2('writer'),
      // Aurora Serverless v2 added 2024 auto-pause scale-to-zero behavior by setting minimum capacity to 0 ACUs, which avoids ACU charges while idle.
      serverlessV2MinCapacity: 0,
      serverlessV2MaxCapacity: 4,
      serverlessV2AutoPauseDuration: Duration.hours(1),
      enableDataApi: true,
      credentials: rds.Credentials.fromGeneratedSecret('postgres'),
      defaultDatabaseName: DATABASE_NAME,
      storageEncrypted: true,
      deletionProtection: false,
      // PoC-only teardown posture. Use RETAIN plus deletion protection for production or shared environments.
      removalPolicy: RemovalPolicy.DESTROY,
      vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
      },
    });

    const cfnCluster = cluster.node.defaultChild as rds.CfnDBCluster;
    cfnCluster.associatedRoles = [
      {
        roleArn: bedrockRole.roleArn,
        featureName: 'Bedrock',
      },
    ];

    cfnCluster.node.addDependency(bedrockRole);

    // Optional advanced path: this associated role is only needed if SQL calls Bedrock through aws_ml and aws_bedrock.invoke_model.
    // The primary PoC path should call Bedrock from the application layer with boto3, then use the RDS Data API for Aurora pgvector.
    // Because this VPC is private isolated with no NAT gateway, the optional SQL-to-Bedrock path also needs Bedrock Runtime network
    // access, for example an interface VPC endpoint, before SQL inference can work. It is not added here to keep the primary PoC lean.

    new cdk.CfnOutput(this, 'ClusterArn', {
      value: cluster.clusterArn,
      description: 'Use as DB_CLUSTER_ARN for the PoC application.',
    });

    new cdk.CfnOutput(this, 'SecretArn', {
      value: cluster.secret!.secretArn,
      description: 'Use as DB_SECRET_ARN for the PoC application.',
    });

    new cdk.CfnOutput(this, 'DatabaseName', {
      value: DATABASE_NAME,
      description: 'Use as DB_NAME for the PoC application.',
    });

    new cdk.CfnOutput(this, 'Region', {
      value: Stack.of(this).region,
      description: 'Use as AWS_REGION for the PoC application.',
    });
  }
}
