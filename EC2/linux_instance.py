import boto3

# --------------------------------
# AWS Session
# --------------------------------

session = boto3.Session(
    profile_name="sravana_test",
    region_name="eu-west-2"
)

ec2 = session.client("ec2")


# --------------------------------
# Existing VPC and Private Subnet
# --------------------------------

VPC_ID = "vpc-084dc161e5a0846db"
PRIVATE_SUBNET_ID = "subnet-0d77a90195a2525e7"


# --------------------------------
# Create Security Group
# --------------------------------

response = ec2.create_security_group(
    GroupName="linux-httpd-sg",
    Description="Security group for private Linux Apache server",
    VpcId=VPC_ID
)

security_group_id = response["GroupId"]

print("Security Group:", security_group_id)


# --------------------------------
# Find latest Amazon Linux 2023 AMI
# --------------------------------

response = ec2.describe_images(
    Owners=["amazon"],
    Filters=[
        {
            "Name": "name",
            "Values": ["al2023-ami-2023*-x86_64"]
        },
        {
            "Name": "state",
            "Values": ["available"]
        }
    ]
)

images = sorted(
    response["Images"],
    key=lambda x: x["CreationDate"],
    reverse=True
)

ami_id = images[0]["ImageId"]

print("AMI:", ami_id)


# --------------------------------
# User Data
# --------------------------------

user_data = """#!/bin/bash

dnf update -y

dnf install -y httpd

systemctl enable httpd
systemctl start httpd

echo "<h1>This is my linux server created through script</h1>" > /var/www/html/index.html
"""


# --------------------------------
# Create EC2
# --------------------------------

response = ec2.run_instances(
    ImageId=ami_id,
    InstanceType="t3.micro",

    MinCount=1,
    MaxCount=1,

    SubnetId=PRIVATE_SUBNET_ID,

    SecurityGroupIds=[
        security_group_id
    ],

    IamInstanceProfile={
        "Name": "AmazonSSMManagedInstanceCore"
    },

    UserData=user_data,

    TagSpecifications=[
        {
            "ResourceType": "instance",
            "Tags": [
                {
                    "Key": "Name",
                    "Value": "Private-Linux-httpd"
                }
            ]
        }
    ]
)

instance_id = response["Instances"][0]["InstanceId"]

print("EC2 Instance:", instance_id)
print("User Data will install Apache automatically.")