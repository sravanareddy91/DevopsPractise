import boto3
import time


# ============================================================
# CONFIGURATION
# ============================================================

PROFILE = "sravana_test"
REGION = "eu-west-2"

# Your existing VPC
VPC_ID = "vpc-084dc161e5a0846db"

# Your existing PRIVATE subnet
PRIVATE_SUBNET_ID = "subnet-027de73c43113fcf8"

# IMPORTANT:
# This must be the IAM INSTANCE PROFILE name, not just the IAM role name.
SSM_INSTANCE_PROFILE = "AmazonSSMManagedInstanceCore"

# Security group name for this Ubuntu server
SECURITY_GROUP_NAME = "private-ubuntu-apache-sg"


# ============================================================
# AWS SESSION
# ============================================================

session = boto3.Session(
    profile_name=PROFILE,
    region_name=REGION
)

ec2 = session.client("ec2")
ssm = session.client("ssm")


# ============================================================
# 1. CREATE SECURITY GROUP
# ============================================================

print("\nCreating Ubuntu security group...")

try:

    response = ec2.create_security_group(
        GroupName=SECURITY_GROUP_NAME,
        Description="Security group for private Ubuntu Apache server",
        VpcId=VPC_ID
    )

    security_group_id = response["GroupId"]

    print("Created Security Group:", security_group_id)

except ec2.exceptions.ClientError as e:

    if "InvalidGroup.Duplicate" in str(e):

        print("Security group already exists.")

        response = ec2.describe_security_groups(
            Filters=[
                {
                    "Name": "group-name",
                    "Values": [SECURITY_GROUP_NAME]
                },
                {
                    "Name": "vpc-id",
                    "Values": [VPC_ID]
                }
            ]
        )

        security_group_id = response["SecurityGroups"][0]["GroupId"]

        print("Using existing Security Group:", security_group_id)

    else:
        raise


# ============================================================
# 2. FIND LATEST UBUNTU 24.04 AMI
# ============================================================

print("\nFinding latest Ubuntu 24.04 AMI...")

response = ec2.describe_images(
    Owners=["099720109477"],
    Filters=[
        {
            "Name": "name",
            "Values": [
                "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"
            ]
        },
        {
            "Name": "state",
            "Values": ["available"]
        },
        {
            "Name": "architecture",
            "Values": ["x86_64"]
        },
        {
            "Name": "root-device-type",
            "Values": ["ebs"]
        },
        {
            "Name": "virtualization-type",
            "Values": ["hvm"]
        }
    ]
)

ubuntu_images = sorted(
    response["Images"],
    key=lambda image: image["CreationDate"],
    reverse=True
)

if not ubuntu_images:
    raise Exception("No Ubuntu AMI found.")

ubuntu_ami_id = ubuntu_images[0]["ImageId"]

print("Ubuntu AMI:", ubuntu_ami_id)


# ============================================================
# 3. USER DATA SCRIPT
# ============================================================

ubuntu_user_data = """#!/bin/bash

# Update package information
apt-get update -y

# Install Apache
apt-get install -y apache2

# Start Apache automatically
systemctl enable apache2
systemctl start apache2

# Create test web page
echo "<h1>This is my ubuntu server created through script</h1>" > /var/www/html/index.html
"""


# ============================================================
# 4. CREATE UBUNTU EC2
# ============================================================

print("\nCreating Ubuntu EC2...")

response = ec2.run_instances(

    ImageId=ubuntu_ami_id,

    InstanceType="t3.micro",

    MinCount=1,
    MaxCount=1,

    # Existing private subnet
    SubnetId=PRIVATE_SUBNET_ID,

    # New Ubuntu-specific security group
    SecurityGroupIds=[
        security_group_id
    ],

    # Existing SSM instance profile
    IamInstanceProfile={
        "Name": SSM_INSTANCE_PROFILE
    },

    # Install Apache automatically
    UserData=ubuntu_user_data,

    TagSpecifications=[
        {
            "ResourceType": "instance",

            "Tags": [
                {
                    "Key": "Name",
                    "Value": "Private-Ubuntu-Apache"
                }
            ]
        }
    ]
)


ubuntu_instance_id = response["Instances"][0]["InstanceId"]

print("Ubuntu Instance ID:", ubuntu_instance_id)


# ============================================================
# 5. WAIT FOR EC2 TO RUN
# ============================================================

print("\nWaiting for EC2 to reach running state...")

ec2.get_waiter("instance_running").wait(
    InstanceIds=[ubuntu_instance_id]
)

print("EC2 is running.")


# ============================================================
# 6. GET PRIVATE IP
# ============================================================

response = ec2.describe_instances(
    InstanceIds=[ubuntu_instance_id]
)

instance = response["Reservations"][0]["Instances"][0]

private_ip = instance.get("PrivateIpAddress")

print("Private IP:", private_ip)


# ============================================================
# 7. WAIT FOR USER DATA
# ============================================================

print("\nWaiting for User Data to install Apache...")

time.sleep(60)


# ============================================================
# 8. RUN CURL THROUGH SSM
# ============================================================

print("\nSending SSM command to Ubuntu...")

try:

    response = ssm.send_command(

        InstanceIds=[
            ubuntu_instance_id
        ],

        DocumentName="AWS-RunShellScript",

        Parameters={
            "commands": [
                "systemctl status apache2 --no-pager",
                "curl http://localhost"
            ]
        }
    )

    command_id = response["Command"]["CommandId"]

    print("SSM Command ID:", command_id)


    # --------------------------------------------------------
    # Wait for SSM command
    # --------------------------------------------------------

    time.sleep(10)


    # --------------------------------------------------------
    # Get command result
    # --------------------------------------------------------

    result = ssm.get_command_invocation(
        CommandId=command_id,
        InstanceId=ubuntu_instance_id
    )

    print("\n========================================")
    print("SSM STATUS")
    print("========================================")

    print(result["Status"])

    print("\n========================================")
    print("OUTPUT")
    print("========================================")

    print(result["StandardOutputContent"])

    print("\n========================================")
    print("ERROR")
    print("========================================")

    print(result["StandardErrorContent"])


except Exception as e:

    print("\nSSM command could not be executed yet.")
    print("Error:", e)

    print("\nYou can check the instance from:")
    print("EC2 → Instances → Private-Ubuntu-Apache")
    print("→ Connect → Session Manager")


# ============================================================
# DONE
# ============================================================

print("\n========================================")
print("UBUNTU SERVER CREATED")
print("========================================")

print("Instance ID:", ubuntu_instance_id)
print("Private IP:", private_ip)
print("Security Group:", security_group_id)

print("\nApache was installed through User Data.")

print("\nTo manually verify through SSM:")
print("sudo systemctl status apache2")
print("curl localhost")