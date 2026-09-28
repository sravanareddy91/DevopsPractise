import boto3
from botocore.exceptions import ClientError

# ============================================================
# CONFIGURATION
# ============================================================

PROFILE = "sravana_test"
REGION = "eu-west-2"

ALB_NAME = "python-application-alb"

LINUX_TG_NAME = "linux-tg-python"
UBUNTU_TG_NAME = "ubuntu-tg-python"

LINUX_PORT = 8080
UBUNTU_PORT = 8090

# Your ALB subnets
SUBNET_1 = "subnet-068a60f30c43f1e9c"
SUBNET_2 = "subnet-0c86ff7e4552d03b5"

# ============================================================
# AWS SESSION
# ============================================================

session = boto3.Session(
    profile_name=PROFILE,
    region_name=REGION
)

ec2 = session.client("ec2")
elbv2 = session.client("elbv2")

print("\n==========================================")
print("AWS ALB SETUP STARTED")
print("==========================================\n")


# ============================================================
# 1. FIND ALB
# ============================================================

print("1. Finding existing ALB...")

try:
    response = elbv2.describe_load_balancers(
        Names=[ALB_NAME]
    )

    alb = response["LoadBalancers"][0]

    ALB_ARN = alb["LoadBalancerArn"]
    ALB_DNS = alb["DNSName"]
    ALB_SG_ID = alb["SecurityGroups"][0]
    VPC_ID = alb["VpcId"]

    print(f"ALB found: {ALB_NAME}")
    print(f"ALB DNS: {ALB_DNS}")
    print(f"VPC: {VPC_ID}")
    print(f"ALB Security Group: {ALB_SG_ID}")

except ClientError as e:
    print("ERROR: ALB not found.")
    print(e)
    exit()


# ============================================================
# 2. FIND TARGET GROUPS
# ============================================================

print("\n2. Finding target groups...")

try:
    linux_tg = elbv2.describe_target_groups(
        Names=[LINUX_TG_NAME]
    )["TargetGroups"][0]

    ubuntu_tg = elbv2.describe_target_groups(
        Names=[UBUNTU_TG_NAME]
    )["TargetGroups"][0]

except ClientError as e:
    print("ERROR: Target group not found.")
    print(e)
    exit()


LINUX_TG_ARN = linux_tg["TargetGroupArn"]
UBUNTU_TG_ARN = ubuntu_tg["TargetGroupArn"]

print(f"Linux TG: {LINUX_TG_NAME}")
print(f"Linux TG port: {linux_tg['Port']}")

print(f"Ubuntu TG: {UBUNTU_TG_NAME}")
print(f"Ubuntu TG port: {ubuntu_tg['Port']}")


# ============================================================
# 3. CHECK TARGET GROUP PORTS
# ============================================================

print("\n3. Checking target group ports...")

if linux_tg["Port"] != LINUX_PORT:
    print(
        f"WARNING: Linux target group is configured for "
        f"port {linux_tg['Port']} instead of {LINUX_PORT}"
    )

if ubuntu_tg["Port"] != UBUNTU_PORT:
    print(
        f"WARNING: Ubuntu target group is configured for "
        f"port {ubuntu_tg['Port']} instead of {UBUNTU_PORT}"
    )


# ============================================================
# 4. ALB SECURITY GROUP
#    Allow users to access ALB on 8080 and 8090
# ============================================================

print("\n4. Configuring ALB security group...")

for port in [LINUX_PORT, UBUNTU_PORT]:

    try:

        ec2.authorize_security_group_ingress(
            GroupId=ALB_SG_ID,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": port,
                    "ToPort": port,
                    "IpRanges": [
                        {
                            "CidrIp": "0.0.0.0/0",
                            "Description": f"ALB listener port {port}"
                        }
                    ]
                }
            ]
        )

        print(f"Allowed inbound TCP {port}")

    except ClientError as e:

        if "InvalidPermission.Duplicate" in str(e):
            print(f"Inbound TCP {port} already allowed")

        else:
            print(f"ERROR configuring port {port}")
            print(e)


# ============================================================
# 5. CONFIGURE EC2 SECURITY GROUPS
#    Allow ALB SG to reach backend servers
# ============================================================

print("\n5. Configuring EC2 security groups...")

# Get Linux targets
linux_targets = elbv2.describe_target_health(
    TargetGroupArn=LINUX_TG_ARN
)["TargetHealthDescriptions"]

# Get Ubuntu targets
ubuntu_targets = elbv2.describe_target_health(
    TargetGroupArn=UBUNTU_TG_ARN
)["TargetHealthDescriptions"]


# ------------------------------------------------------------
# Linux EC2
# ------------------------------------------------------------

for target in linux_targets:

    instance_id = target["Target"]["Id"]

    print(f"Linux instance: {instance_id}")

    instance = ec2.describe_instances(
        InstanceIds=[instance_id]
    )["Reservations"][0]["Instances"][0]

    security_groups = instance["SecurityGroups"]

    for sg in security_groups:

        sg_id = sg["GroupId"]

        try:

            ec2.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        "IpProtocol": "tcp",
                        "FromPort": LINUX_PORT,
                        "ToPort": LINUX_PORT,
                        "UserIdGroupPairs": [
                            {
                                "GroupId": ALB_SG_ID,
                                "Description": "Allow ALB to Linux Apache"
                            }
                        ]
                    }
                ]
            )

            print(
                f"Allowed ALB SG -> {sg_id} TCP {LINUX_PORT}"
            )

        except ClientError as e:

            if "InvalidPermission.Duplicate" in str(e):
                print(
                    f"Rule already exists: {sg_id} TCP {LINUX_PORT}"
                )

            else:
                print(e)


# ------------------------------------------------------------
# Ubuntu EC2
# ------------------------------------------------------------

for target in ubuntu_targets:

    instance_id = target["Target"]["Id"]

    print(f"Ubuntu instance: {instance_id}")

    instance = ec2.describe_instances(
        InstanceIds=[instance_id]
    )["Reservations"][0]["Instances"][0]

    security_groups = instance["SecurityGroups"]

    for sg in security_groups:

        sg_id = sg["GroupId"]

        try:

            ec2.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        "IpProtocol": "tcp",
                        "FromPort": UBUNTU_PORT,
                        "ToPort": UBUNTU_PORT,
                        "UserIdGroupPairs": [
                            {
                                "GroupId": ALB_SG_ID,
                                "Description": "Allow ALB to Ubuntu Apache"
                            }
                        ]
                    }
                ]
            )

            print(
                f"Allowed ALB SG -> {sg_id} TCP {UBUNTU_PORT}"
            )

        except ClientError as e:

            if "InvalidPermission.Duplicate" in str(e):
                print(
                    f"Rule already exists: {sg_id} TCP {UBUNTU_PORT}"
                )

            else:
                print(e)


# ============================================================
# 6. DELETE OLD LISTENERS
# ============================================================

print("\n6. Removing existing listeners...")

listeners = elbv2.describe_listeners(
    LoadBalancerArn=ALB_ARN
)["Listeners"]

for listener in listeners:

    port = listener["Port"]
    listener_arn = listener["ListenerArn"]

    print(f"Deleting listener on port {port}")

    elbv2.delete_listener(
        ListenerArn=listener_arn
    )


# ============================================================
# 7. CREATE LINUX LISTENER :8080
# ============================================================

print("\n7. Creating Linux listener on port 8080...")

linux_listener = elbv2.create_listener(
    LoadBalancerArn=ALB_ARN,
    Protocol="HTTP",
    Port=LINUX_PORT,
    DefaultActions=[
        {
            "Type": "forward",
            "TargetGroupArn": LINUX_TG_ARN
        }
    ]
)

print("Linux listener created:")
print(f"ALB :8080 -> {LINUX_TG_NAME}")


# ============================================================
# 8. CREATE UBUNTU LISTENER :8090
# ============================================================

print("\n8. Creating Ubuntu listener on port 8090...")

ubuntu_listener = elbv2.create_listener(
    LoadBalancerArn=ALB_ARN,
    Protocol="HTTP",
    Port=UBUNTU_PORT,
    DefaultActions=[
        {
            "Type": "forward",
            "TargetGroupArn": UBUNTU_TG_ARN
        }
    ]
)

print("Ubuntu listener created:")
print(f"ALB :8090 -> {UBUNTU_TG_NAME}")


# ============================================================
# 9. VERIFY LISTENERS
# ============================================================

print("\n9. Verifying listeners...")

listeners = elbv2.describe_listeners(
    LoadBalancerArn=ALB_ARN
)["Listeners"]

for listener in listeners:

    print(
        f"Listener: {listener['Protocol']} "
        f"port {listener['Port']}"
    )


# ============================================================
# 10. CHECK TARGET HEALTH
# ============================================================

print("\n10. Checking target health...")

print("\nLinux target health:")

linux_health = elbv2.describe_target_health(
    TargetGroupArn=LINUX_TG_ARN
)

for target in linux_health["TargetHealthDescriptions"]:

    print(
        f"Instance: {target['Target']['Id']} "
        f"Port: {target['Target']['Port']} "
        f"State: {target['TargetHealth']['State']}"
    )


print("\nUbuntu target health:")

ubuntu_health = elbv2.describe_target_health(
    TargetGroupArn=UBUNTU_TG_ARN
)

for target in ubuntu_health["TargetHealthDescriptions"]:

    print(
        f"Instance: {target['Target']['Id']} "
        f"Port: {target['Target']['Port']} "
        f"State: {target['TargetHealth']['State']}"
    )


# ============================================================
# 11. FINAL OUTPUT
# ============================================================

print("\n==========================================")
print("ALB SETUP COMPLETED")
print("==========================================")

print("\nALB DNS:")
print(ALB_DNS)

print("\nLinux Apache:")
print(f"http://{ALB_DNS}:8080")

print("\nUbuntu Apache:")
print(f"http://{ALB_DNS}:8090")

print("\nExpected traffic:")
print(
    f"ALB :8080  -->  Linux Target Group  -->  Linux EC2 :{LINUX_PORT}"
)

print(
    f"ALB :8090  -->  Ubuntu Target Group  -->  Ubuntu EC2 :{UBUNTU_PORT}"
)

print("\n==========================================")