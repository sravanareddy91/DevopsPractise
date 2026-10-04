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

# Existing EC2 instances
LINUX_INSTANCE_ID = "i-08c341ca31a5be8e4"
UBUNTU_INSTANCE_ID = "i-0dcf2be733d5790b5"

# Existing EC2 security groups
LINUX_SG_ID = "sg-028ccee5b84958125"
UBUNTU_SG_ID = "sg-0146db60e6f3a1ae5"

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


# ============================================================
# 1. GET EXISTING VPC
# ============================================================

print("\nVPC:", VPC_ID)


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


# ============================================================
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
            "Id": LINUX_INSTANCE_ID,
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
            "Id": UBUNTU_INSTANCE_ID,
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

        GroupId=LINUX_SG_ID,

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

        GroupId=UBUNTU_SG_ID,

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