import boto3
import time

# ============================================================
# CONFIGURATION
# ============================================================

PROFILE = "sravana_test"
REGION = "eu-west-2"

# Existing VPC
VPC_ID = "vpc-084dc161e5a0846db"

# Existing PUBLIC subnets
# ALB must be placed in at least two AZs
PUBLIC_SUBNET_1 = "subnet-0a121a2107fa5698c"
PUBLIC_SUBNET_2 = "subnet-0f359573e71feeb1b"

# Private subnet - used by EC2 instances
PRIVATE_SUBNET_ID = "subnet-0d77a90195a2525e7"

# SSM Instance
SSM_INSTANCE_PROFILE = "AmazonSSMManagedInstanceCore"

# ALB names
ALB_NAME = "practice-alb"

LINUX_TG_NAME = "linux-tg"
UBUNTU_TG_NAME = "ubuntu-tg"

ALB_SG_NAME = "practice-alb-sg"

# ============================================================
# AWS SESSION
# ============================================================

session = boto3.Session(
    profile_name=PROFILE,
    region_name=REGION
)

ec2 = session.client("ec2")
elbv2 = session.client("elbv2")


# --------------------------------
# Create Linux Security Group
# --------------------------------
print("\nCreating Linux security group...")

try:

    response = ec2.create_security_group(
        GroupName="linux-httpd-sg",
        Description="Security group for private Linux Apache server",
        VpcId=VPC_ID
    )

    linux_sg_id = response["GroupId"]

    print("Created Security Group:", linux_sg_id)

except ec2.exceptions.ClientError as e:

    if "InvalidGroup.Duplicate" in str(e):

        print("Security group already exists.")

        response = ec2.describe_security_groups(
            Filters=[
                {
                    "Name": "group-name",
                    "Values": ["linux-httpd-sg"]
                },
                {
                    "Name": "vpc-id",
                    "Values": [VPC_ID]
                }
            ]
        )

        linux_sg_id = response["SecurityGroups"][0]["GroupId"]

        print("Using existing Security Group:", linux_sg_id)

    else:
        raise
# ============================================================
# 1. CREATE UBUNTU SECURITY GROUP
# ============================================================

print("\nCreating Ubuntu security group...")

try:

    response = ec2.create_security_group(
        GroupName="Ubuntu-apache-sg",
        Description="Security group for private Ubuntu Apache server",
        VpcId=VPC_ID
    )

    ubuntu_sg_id = response["GroupId"]

    print("Created Security Group:", ubuntu_sg_id)

except ec2.exceptions.ClientError as e:

    if "InvalidGroup.Duplicate" in str(e):

        print("Security group already exists.")

        response = ec2.describe_security_groups(
            Filters=[
                {
                    "Name": "group-name",
                    "Values": ["Ubuntu-apache-sg"]
                },
                {
                    "Name": "vpc-id",
                    "Values": [VPC_ID]
                }
            ]
        )

        ubuntu_sg_id = response["SecurityGroups"][0]["GroupId"]

        print("Using existing Security Group:", ubuntu_sg_id)

    else:
        raise

# ============================================================
# 2. CREATE ALB SECURITY GROUP
# ============================================================

print("\nCreating ALB Security Group...")

try:

    response = ec2.create_security_group(
        GroupName=ALB_SG_NAME,
        Description="Security group for practice Application Load Balancer",
        VpcId=VPC_ID
    )

    alb_sg_id = response["GroupId"]

    print("Created ALB Security Group:", alb_sg_id)

except ec2.exceptions.ClientError as e:

    if "InvalidGroup.Duplicate" in str(e):

        print("ALB Security Group already exists.")

        response = ec2.describe_security_groups(
            Filters=[
                {
                    "Name": "group-name",
                    "Values": [ALB_SG_NAME]
                },
                {
                    "Name": "vpc-id",
                    "Values": [VPC_ID]
                }
            ]
        )

        alb_sg_id = response["SecurityGroups"][0]["GroupId"]

        print("Using existing ALB Security Group:", alb_sg_id)

    else:
        raise

# ============================================================
# 3. ADD INBOUND RULES TO ALB SECURITY GROUP
# ============================================================

print("\nAdding ALB inbound rules...")

try:

    ec2.authorize_security_group_ingress(
        GroupId=alb_sg_id,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 8080,
                "ToPort": 8080,
                "IpRanges": [
                    {
                        "CidrIp": "151.229.116.118/32"
                    }
                ]
            },
            {
                "IpProtocol": "tcp",
                "FromPort": 8090,
                "ToPort": 8090,
                "IpRanges": [
                    {
                        "CidrIp": "151.229.116.118/32"
                    }
                ]
            }
        ]
    )

    print("ALB inbound rules added.")

except ec2.exceptions.ClientError as e:

    if "InvalidPermission.Duplicate" in str(e):

        print("ALB inbound rules already exist.")

    else:
        raise

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

# Change Apache from port 80 to port 8080
sed -i 's/^Listen 80$/Listen 8080/' /etc/httpd/conf/httpd.conf

systemctl enable httpd
systemctl start httpd

echo "<h1>This is my linux server created through script</h1>" > /var/www/html/index.html
"""

# --------------------------------
# Create Linux EC2
# --------------------------------

response = ec2.run_instances(
    ImageId=ami_id,
    InstanceType="t3.micro",

    MinCount=1,
    MaxCount=1,

    SubnetId=PRIVATE_SUBNET_ID,

    SecurityGroupIds=[
        linux_sg_id
    ],

    IamInstanceProfile={
        "Name": SSM_INSTANCE_PROFILE
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

linux_instance_id = response["Instances"][0]["InstanceId"]

print("EC2 Instance:", linux_instance_id)
print("User Data will install Apache automatically.")


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
apt update -y

# Install Apache
apt install -y apache2

# Change Apache from port 80 to port 8090
sed -i 's/^Listen 80$/Listen 8090/' /etc/apache2/ports.conf
sed -i 's/<VirtualHost \\*:80>/<VirtualHost *:8090>/' /etc/apache2/sites-available/000-default.conf

# Create webpage
echo "<h1>This is my Ubuntu server created through script - Port 8090</h1>" > /var/www/html/index.html

# Start Apache automatically
systemctl enable apache2
systemctl restart apache2
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
        ubuntu_sg_id
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
print("Security Group:", ubuntu_sg_id)

print("\nApache was installed through User Data.")

print("\nTo manually verify through SSM:")
print("sudo systemctl status apache2")
print("curl localhost")

#============================================================
# 4. CREATE ALB
# ============================================================

print("\nCreating Application Load Balancer...")

response = elbv2.create_load_balancer(

    Name=ALB_NAME,

    Subnets=[
        PUBLIC_SUBNET_1,
        PUBLIC_SUBNET_2
    ],

    SecurityGroups=[
        alb_sg_id
    ],

    Scheme="internet-facing",

    Type="application",

    IpAddressType="ipv4"
)

load_balancer = response["LoadBalancers"][0]

alb_arn = load_balancer["LoadBalancerArn"]
alb_dns = load_balancer["DNSName"]

print("ALB ARN:", alb_arn)
print("ALB DNS:", alb_dns)

# ============================================================
# 5. WAIT FOR ALB
# ============================================================

print("\nWaiting for ALB to become active...")

waiter = elbv2.get_waiter("load_balancer_available")

waiter.wait(
    LoadBalancerArns=[
        alb_arn
    ]
)

print("ALB is active.")


# ============================================================
# 6. CREATE LINUX TARGET GROUP
# ============================================================

print("\nCreating Linux Target Group...")

response = elbv2.create_target_group(

    Name=LINUX_TG_NAME,

    Protocol="HTTP",

    Port=8080,

    VpcId=VPC_ID,

    TargetType="instance",

    HealthCheckProtocol="HTTP",

    HealthCheckPort="8080",

    HealthCheckPath="/",

    Matcher={
        "HttpCode": "200"
    }
)

linux_tg_arn = response["TargetGroups"][0]["TargetGroupArn"]

print("Linux Target Group:", linux_tg_arn)

# ============================================================
# 7. CREATE UBUNTU TARGET GROUP
# ============================================================

print("\nCreating Ubuntu Target Group...")

response = elbv2.create_target_group(

    Name=UBUNTU_TG_NAME,

    Protocol="HTTP",

    Port=8090,

    VpcId=VPC_ID,

    TargetType="instance",

    HealthCheckProtocol="HTTP",

    HealthCheckPort="8090",

    HealthCheckPath="/",

    Matcher={
        "HttpCode": "200"
    }
)

ubuntu_tg_arn = response["TargetGroups"][0]["TargetGroupArn"]

print("Ubuntu Target Group:", ubuntu_tg_arn)

# ============================================================
# 8. REGISTER LINUX EC2
# ============================================================

print("\nRegistering Linux EC2...")

elbv2.register_targets(

    TargetGroupArn=linux_tg_arn,

    Targets=[
        {
            "Id": linux_instance_id,
            "Port": 8080
        }
    ]
)

print("Linux EC2 registered on port 8080.")

# ============================================================
# 9. REGISTER UBUNTU EC2
# ============================================================

print("\nRegistering Ubuntu EC2...")

elbv2.register_targets(

    TargetGroupArn=ubuntu_tg_arn,

    Targets=[
        {
            "Id": ubuntu_instance_id,
            "Port": 8090
        }
    ]
)

print("Ubuntu EC2 registered on port 8090.")

# ============================================================
# 10. CREATE LISTENER ON PORT 8080
# ============================================================

print("\nCreating ALB listener on port 8080...")

response = elbv2.create_listener(

    LoadBalancerArn=alb_arn,

    Protocol="HTTP",

    Port=8080,

    DefaultActions=[
        {
            "Type": "forward",

            "TargetGroupArn": linux_tg_arn
        }
    ]
)

linux_listener_arn = response["Listeners"][0]["ListenerArn"]

print("Linux listener created:", linux_listener_arn)

# ============================================================
# 11. CREATE LISTENER ON PORT 8090
# ============================================================

print("\nCreating ALB listener on port 8090...")

response = elbv2.create_listener(

    LoadBalancerArn=alb_arn,

    Protocol="HTTP",

    Port=8090,

    DefaultActions=[
        {
            "Type": "forward",

            "TargetGroupArn": ubuntu_tg_arn
        }
    ]
)

ubuntu_listener_arn = response["Listeners"][0]["ListenerArn"]

print("Ubuntu listener created:", ubuntu_listener_arn)

# ============================================================
# 12. UPDATE EC2 SECURITY GROUPS
# ============================================================

print("\nAdding ALB → EC2 security group rules...")

# ------------------------------------------------------------
# Linux EC2 - allow 8080 from ALB
# ------------------------------------------------------------

try:

    ec2.authorize_security_group_ingress(

        GroupId=linux_sg_id,

        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 8080,
                "ToPort": 8080,

                "UserIdGroupPairs": [
                    {
                        "GroupId": alb_sg_id
                    }
                ]
            }
        ]
    )

    print("Linux SG: ALB → port 8080 allowed.")

except ec2.exceptions.ClientError as e:

    if "InvalidPermission.Duplicate" in str(e):

        print("Linux SG rule already exists.")

    else:
        raise

# ------------------------------------------------------------
# Ubuntu EC2 - allow 8090 from ALB
# ------------------------------------------------------------

try:

    ec2.authorize_security_group_ingress(

        GroupId=ubuntu_sg_id,

        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 8090,
                "ToPort": 8090,

                "UserIdGroupPairs": [
                    {
                        "GroupId": alb_sg_id
                    }
                ]
            }
        ]
    )

    print("Ubuntu SG: ALB → port 8090 allowed.")

except ec2.exceptions.ClientError as e:

    if "InvalidPermission.Duplicate" in str(e):

        print("Ubuntu SG rule already exists.")

    else:
        raise

# ============================================================
# 13. WAIT FOR TARGET HEALTH
# ============================================================

print("\nWaiting for target health checks...")

time.sleep(20)

# ============================================================
# 14. CHECK LINUX TARGET
# ============================================================

print("\nChecking Linux target health...")

response = elbv2.describe_target_health(
    TargetGroupArn=linux_tg_arn
)

for target in response["TargetHealthDescriptions"]:

    print(
        "Linux:",
        target["Target"]["Id"],
        target["TargetHealth"]["State"]
    )

# ============================================================
# 15. CHECK UBUNTU TARGET
# ============================================================

print("\nChecking Ubuntu target health...")

response = elbv2.describe_target_health(
    TargetGroupArn=ubuntu_tg_arn
)

for target in response["TargetHealthDescriptions"]:

    print(
        "Ubuntu:",
        target["Target"]["Id"],
        target["TargetHealth"]["State"]
    )

# ============================================================
# DONE
# ============================================================

print("\n==============================================")
print("ALB CREATED SUCCESSFULLY")
print("==============================================")

print("\nALB DNS:")
print(alb_dns)

print("\nLinux:")
print(f"http://{alb_dns}:8080")

print("\nUbuntu:")
print(f"http://{alb_dns}:8090")

print("\nArchitecture:")
print("ALB :8080 → Linux TG → Linux EC2 :8080")
print("ALB :8090 → Ubuntu TG → Ubuntu EC2 :8090")





