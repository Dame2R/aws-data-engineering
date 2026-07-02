#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { RagPocStack } from '../lib/rag-poc-stack';

const app = new cdk.App();

new RagPocStack(app, 'RagPocStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
