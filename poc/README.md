# AWS RAG PoC Runbook

This PoC was scaffolded but NOT deployed by the assistant (no AWS credentials, and deployment is a manual user step). Review IAM and cost before deploying.

## Overview

This proof-of-concept provisions a small AWS data layer for Retrieval Augmented Generation (RAG). The application code is expected to live under `poc/app` and call AWS APIs with boto3.

```text
User
  |
  v
Python app in poc/app (boto3)
  | \
  |  +--> Amazon Bedrock embeddings
  |  |      EMBED_MODEL_ID default: amazon.titan-embed-text-v2:0
  |  |
  |  +--> Aurora PostgreSQL with pgvector via RDS Data API
  |         DB_CLUSTER_ARN, DB_SECRET_ARN, DB_NAME
  |
  +--> Amazon Bedrock LLM generation
         GEN_MODEL_ID selected by user
```

Infrastructure components:

- A VPC across 2 Availability Zones with private isolated subnets only and no NAT gateway.
- An Amazon Aurora PostgreSQL Serverless v2 cluster with RDS Data API enabled.
- A generated Secrets Manager master secret for the `postgres` user.
- Optional Aurora Machine Learning IAM role for an advanced in-SQL Bedrock inference path.

The primary PoC path is application-layer Bedrock calls plus Aurora pgvector queries through the RDS Data API. The optional IAM role is only needed if you later enable SQL calls such as `aws_bedrock.invoke_model` through the `aws_ml` extension. Because the VPC has private isolated subnets only and no NAT gateway, that optional in-SQL Bedrock path also requires Bedrock Runtime network access, such as an interface VPC endpoint, before SQL inference can work.

## Prerequisites

- Node.js 18 or newer.
- AWS CDK v2, run through `npx` from the CDK app directory.
- AWS credentials configured for the target account and region with permissions to deploy VPC, RDS, Secrets Manager, IAM, and CloudFormation resources.
- Amazon Bedrock model access enabled in the target region for:
  - Titan Text Embeddings V2 (Amazon-owned, no Marketplace subscription needed).
  - A generation model. Amazon Nova (for example `eu.amazon.nova-pro-v1:0`) is Amazon-owned and works without an AWS Marketplace subscription. Third-party models such as Anthropic Claude require an AWS Marketplace model subscription, which in many enterprise accounts must be enabled centrally because developer roles lack `aws-marketplace:Subscribe`.
- Python 3.11 or newer.
- Application dependencies from `poc/requirements.txt`, including boto3.

## Deploy

Deployment is manual. Run these commands from the repository root unless noted.

```bash
cd poc/cdk
npm install
npx cdk bootstrap
npx cdk deploy
```

After deployment, copy the CloudFormation outputs:

- `ClusterArn` maps to `DB_CLUSTER_ARN`.
- `SecretArn` maps to `DB_SECRET_ARN`.
- `DatabaseName` maps to `DB_NAME` and should be `ragdemo`.
- `Region` maps to `AWS_REGION`.

## Configure

Choose a Bedrock generation model that your account can invoke. Amazon Nova is the default and recommended choice because it is Amazon-owned and needs no AWS Marketplace subscription. In `eu-central-1` (Frankfurt) use the cross-region inference profile `eu.amazon.nova-pro-v1:0` (or `eu.amazon.nova-lite-v1:0` for lower cost). To use Anthropic Claude instead, set `GEN_MODEL_ID` to an accessible Claude profile such as `eu.anthropic.claude-sonnet-4-5-20250929-v1:0`, but note that Claude requires an AWS Marketplace model subscription enabled for the account. The application auto-detects Nova versus Claude from the model ID and sends the matching request schema.

```bash
export AWS_REGION="<Region output>"
export DB_CLUSTER_ARN="<ClusterArn output>"
export DB_SECRET_ARN="<SecretArn output>"
export DB_NAME="ragdemo"
export EMBED_MODEL_ID="amazon.titan-embed-text-v2:0"
export GEN_MODEL_ID="eu.amazon.nova-pro-v1:0"
export VECTOR_DIM="1024"
```

## Caller IAM permissions

The application runs on your machine and calls AWS with your local credentials (for example `AWS_PROFILE` or environment credentials). That identity, not the CDK deploy role, needs runtime permissions:

- `rds-data:ExecuteStatement` on the cluster ARN.
- `secretsmanager:GetSecretValue` on the cluster master secret ARN.
- `bedrock:InvokeModel` on the embedding and generation models or inference profiles.

If your local identity is already an administrator you can skip the policy below. Otherwise attach a least-privilege policy and replace the ARNs, region, and account ID:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DataApi",
      "Effect": "Allow",
      "Action": "rds-data:ExecuteStatement",
      "Resource": "<ClusterArn output>"
    },
    {
      "Sid": "ReadDbSecret",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "<SecretArn output>"
    },
    {
      "Sid": "InvokeBedrock",
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": [
        "arn:aws:bedrock:<region>::foundation-model/amazon.titan-embed-text-v2:0",
        "arn:aws:bedrock:<region>:<account-id>:inference-profile/eu.anthropic.claude-3-5-sonnet-20240620-v1:0"
      ]
    }
  ]
}
```

## Install app dependencies

Run from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r poc/requirements.txt
```

## Seed

Run the ingestion script from the repository root:

```bash
python poc/app/ingest.py
```

The script is expected to create or use the pgvector schema, embed the sample corpus with Bedrock, and store vectors in Aurora PostgreSQL through the RDS Data API.

## Query

Run a RAG question from the repository root:

```bash
python poc/app/query.py "How does Aurora Serverless v2 scale to zero?"
```

The script is expected to embed the question, retrieve similar chunks from Aurora pgvector, and call the configured Bedrock generation model.

Run `query.py` without an argument to start an interactive chat loop, which is convenient for a live demo recording:

```bash
python poc/app/query.py
```

The Aurora Serverless v2 minimum capacity is 0 ACU, so the cluster pauses when idle. The first `ingest.py` or `query.py` run after a pause can take a few extra seconds while the cluster resumes. The Data API client retries `DatabaseResumingException` automatically, so no manual action is needed.

## Teardown

Run from the CDK app directory:

```bash
cd poc/cdk
npx cdk destroy
```

This stack is configured for PoC teardown with `RemovalPolicy.DESTROY` and deletion protection disabled. Do not use that posture for production or shared environments.

## Cost notes

- Aurora Serverless v2 charges for ACU-hours while instances are active. This PoC sets the minimum capacity to 0 ACUs so Aurora can auto-pause when idle and reduce compute cost.
- Bedrock embeddings and generation are billed per model usage. Embedding corpus size, query volume, generated tokens, and selected model drive cost.
- No NAT gateway is provisioned, which avoids hourly NAT gateway and data processing charges.
- A Bedrock Runtime interface VPC endpoint is not provisioned. Add it only if you enable the optional in-SQL Aurora Machine Learning path, and account for PrivateLink endpoint hourly and data processing charges.
- Storage, backups, Secrets Manager, CloudWatch, and CloudFormation resources can still incur charges.

## Security notes

- The application should authenticate to Aurora through the RDS Data API using IAM permissions and the generated Secrets Manager secret.
- The database master password is generated and stored in AWS Secrets Manager. Do not copy secrets into source control.
- IAM policies should be reviewed before deployment. The optional Aurora Machine Learning role allows `bedrock:InvokeModel` for Bedrock foundation models and inference profiles in the deployed region.
- The CDK stack uses least-privilege intent for the optional Bedrock role, but production should restrict model ARNs to approved models or inference profiles.
- The optional in-SQL Bedrock path needs network connectivity from Aurora to Bedrock Runtime. In this no-NAT isolated VPC, add a Bedrock Runtime interface VPC endpoint if you enable that path.
- The VPC has only private isolated subnets and no NAT gateway. No in-VPC application compute is required for this PoC because the app uses public AWS APIs from outside the VPC.
- `RemovalPolicy.DESTROY` and `deletionProtection: false` are PoC-only settings for easy teardown. Production should use retention, backups, deletion protection, and tighter IAM boundaries.
