import boto3
import time
import base64


# ============================================================
# CONFIGURATION
# ============================================================

PROFILE = "sravana_test"
REGION = "eu-west-2"

VPC_ID = "vpc-084dc161e5a0846db"

# Public subnets for ALB
PUBLIC_SUBNET_1 = "subnet-0a121a2107fa5698c"
PUBLIC_SUBNET_2 = "subnet-0f359573e71feeb1b"

# Private subnet for EC2 / ASG
PRIVATE_SUBNET_ID = "subnet-0d77a90195a2525e7"

# Existing IAM instance profile used by your EC2 instances
SSM_INSTANCE_PROFILE = "AmazonSSMManagedInstanceCore"


# ============================================================
# RESOURCE NAMES
# ============================================================

ALB_NAME = "practice-alb"

ALB_SG_NAME = "practice-alb-sg"

LINUX_SG_NAME = "linux-httpd-sg"
UBUNTU_SG_NAME = "Ubuntu-apache-sg"

LINUX_TG_NAME = "linux-tg"
UBUNTU_TG_NAME = "ubuntu-tg"

LINUX_LAUNCH_TEMPLATE_NAME = "linux-asg-launch-template"
UBUNTU_LAUNCH_TEMPLATE_NAME = "ubuntu-asg-launch-template"

LINUX_ASG_NAME = "linux-apache-asg"
UBUNTU_ASG_NAME = "ubuntu-apache-asg"


# ============================================================
# ALB ACCESS
# ============================================================
# For learning this allows access from anywhere.
#
# For better security, change this to your own public IP:
# ALB_ALLOWED_CIDR = "YOUR_PUBLIC_IP/32"
# ============================================================

ALB_ALLOWED_CIDR = "0.0.0.0/0"


# ============================================================
# CREATE SESSION
# ============================================================

print("\nCreating boto3 session...")

session = boto3.Session(
    profile_name=PROFILE,
    region_name=REGION
)

ec2 = session.client("ec2")
elbv2 = session.client("elbv2")
autoscaling = session.client("autoscaling")

print("Session created.")
print(f"Region: {REGION}")
print(f"VPC: {VPC_ID}")


# ============================================================
# HELPER FUNCTION - GET SECURITY GROUP
# ============================================================

def get_security_group_id(group_name):

    response = ec2.describe_security_groups(
        Filters=[
            {
                "Name": "group-name",
                "Values": [group_name]
            },
            {
                "Name": "vpc-id",
                "Values": [VPC_ID]
            }
        ]
    )

    if response["SecurityGroups"]:
        return response["SecurityGroups"][0]["GroupId"]

    return None


# ============================================================
# CREATE LINUX SECURITY GROUP
# ============================================================

print("\nCreating / finding Linux security group...")

linux_sg_id = get_security_group_id(LINUX_SG_NAME)

if linux_sg_id:

    print(f"Linux SG already exists: {linux_sg_id}")

else:

    response = ec2.create_security_group(
        GroupName=LINUX_SG_NAME,
        Description="Security group for Linux Apache ASG",
        VpcId=VPC_ID
    )

    linux_sg_id = response["GroupId"]

    print(f"Created Linux SG: {linux_sg_id}")


# ============================================================
# CREATE UBUNTU SECURITY GROUP
# ============================================================

print("\nCreating / finding Ubuntu security group...")

ubuntu_sg_id = get_security_group_id(UBUNTU_SG_NAME)

if ubuntu_sg_id:

    print(f"Ubuntu SG already exists: {ubuntu_sg_id}")

else:

    response = ec2.create_security_group(
        GroupName=UBUNTU_SG_NAME,
        Description="Security group for Ubuntu Apache ASG",
        VpcId=VPC_ID
    )

    ubuntu_sg_id = response["GroupId"]

    print(f"Created Ubuntu SG: {ubuntu_sg_id}")


# ============================================================
# CREATE ALB SECURITY GROUP
# ============================================================

print("\nCreating / finding ALB security group...")

alb_sg_id = get_security_group_id(ALB_SG_NAME)

if alb_sg_id:

    print(f"ALB SG already exists: {alb_sg_id}")

else:

    response = ec2.create_security_group(
        GroupName=ALB_SG_NAME,
        Description="Security group for Application Load Balancer",
        VpcId=VPC_ID
    )

    alb_sg_id = response["GroupId"]

    print(f"Created ALB SG: {alb_sg_id}")


# ============================================================
# ALB SECURITY GROUP - PORT 8080
# ============================================================

print("\nAdding ALB inbound rule for port 8080...")

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
                        "CidrIp": ALB_ALLOWED_CIDR
                    }
                ]
            }
        ]
    )

    print("Port 8080 rule added.")

except ec2.exceptions.ClientError as e:

    if "InvalidPermission.Duplicate" in str(e):

        print("Port 8080 rule already exists.")

    else:

        raise


# ============================================================
# ALB SECURITY GROUP - PORT 8090
# ============================================================

print("\nAdding ALB inbound rule for port 8090...")

try:

    ec2.authorize_security_group_ingress(
        GroupId=alb_sg_id,
        IpPermissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 8090,
                "ToPort": 8090,
                "IpRanges": [
                    {
                        "CidrIp": ALB_ALLOWED_CIDR
                    }
                ]
            }
        ]
    )

    print("Port 8090 rule added.")

except ec2.exceptions.ClientError as e:

    if "InvalidPermission.Duplicate" in str(e):

        print("Port 8090 rule already exists.")

    else:

        raise


# ============================================================
# FIND AMAZON LINUX 2023 AMI
# ============================================================

print("\nFinding latest Amazon Linux 2023 AMI...")

linux_ami_response = ec2.describe_images(
    Owners=["amazon"],
    Filters=[
        {
            "Name": "name",
            "Values": [
                "al2023-ami-2023.*-x86_64"
            ]
        },
        {
            "Name": "state",
            "Values": ["available"]
        },
        {
            "Name": "architecture",
            "Values": ["x86_64"]
        }
    ]
)

linux_images = sorted(
    linux_ami_response["Images"],
    key=lambda x: x["CreationDate"],
    reverse=True
)

if not linux_images:

    raise Exception("Could not find Amazon Linux 2023 AMI.")

linux_ami_id = linux_images[0]["ImageId"]

print(f"Amazon Linux AMI: {linux_ami_id}")


# ============================================================
# FIND UBUNTU 24.04 AMI
# ============================================================

print("\nFinding latest Ubuntu 24.04 AMI...")

ubuntu_ami_response = ec2.describe_images(
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
        }
    ]
)

ubuntu_images = sorted(
    ubuntu_ami_response["Images"],
    key=lambda x: x["CreationDate"],
    reverse=True
)

if not ubuntu_images:

    raise Exception("Could not find Ubuntu 24.04 AMI.")

ubuntu_ami_id = ubuntu_images[0]["ImageId"]

print(f"Ubuntu AMI: {ubuntu_ami_id}")


# ============================================================
# LINUX USER DATA
# ============================================================

linux_user_data = """#!/bin/bash

# Update packages
dnf update -y

# Install Apache
dnf install -y httpd

# Change Apache port from 80 to 8080
sed -i 's/^Listen 80$/Listen 8080/' /etc/httpd/conf/httpd.conf

# Create web page
cat > /var/www/html/index.html <<EOF
<h1>This is my Linux ASG server</h1>
<p>Operating System: Amazon Linux 2023</p>
<p>Apache Port: 8080</p>
<p>Hostname: $(hostname)</p>
EOF

# Enable and start Apache
systemctl enable httpd
systemctl restart httpd
"""


# ============================================================
# UBUNTU USER DATA
# ============================================================

ubuntu_user_data = """#!/bin/bash

# Update packages
apt update -y

# Install Apache
apt install -y apache2

# Change Apache port from 80 to 8090
sed -i 's/^Listen 80$/Listen 8090/' /etc/apache2/ports.conf

# Change VirtualHost from 80 to 8090
sed -i 's/<VirtualHost \\\\*:80>/<VirtualHost *:8090>/' /etc/apache2/sites-available/000-default.conf

# Create web page
cat > /var/www/html/index.html <<EOF
<h1>This is my Ubuntu ASG server</h1>
<p>Operating System: Ubuntu 24.04</p>
<p>Apache Port: 8090</p>
<p>Hostname: $(hostname)</p>
EOF

# Enable and restart Apache
systemctl enable apache2
systemctl restart apache2
"""


# ============================================================
# CREATE LINUX LAUNCH TEMPLATE
# ============================================================

print("\n============================================================")
print("CREATING LINUX LAUNCH TEMPLATE")
print("============================================================")

try:

    response = ec2.create_launch_template(

        LaunchTemplateName=LINUX_LAUNCH_TEMPLATE_NAME,

        VersionDescription="Linux Apache 8080",

        LaunchTemplateData={

            "ImageId": linux_ami_id,

            "InstanceType": "t3.micro",

            "SecurityGroupIds": [
                linux_sg_id
            ],

            "IamInstanceProfile": {
                "Name": SSM_INSTANCE_PROFILE
            },

            "UserData": base64.b64encode(
                linux_user_data.encode()
            ).decode(),

            "TagSpecifications": [
                {
                    "ResourceType": "instance",

                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": "Linux-ASG-Apache-8080"
                        }
                    ]
                }
            ]
        }
    )

    linux_launch_template_id = response[
        "LaunchTemplate"
    ]["LaunchTemplateId"]

    print(
        f"Linux Launch Template created: "
        f"{linux_launch_template_id}"
    )

except ec2.exceptions.ClientError as e:

    if "InvalidLaunchTemplateName.AlreadyExistsException" in str(e):

        print("Linux Launch Template already exists.")

        response = ec2.describe_launch_templates(
            LaunchTemplateNames=[
                LINUX_LAUNCH_TEMPLATE_NAME
            ]
        )

        linux_launch_template_id = response[
            "LaunchTemplates"
        ][0]["LaunchTemplateId"]

        print(
            f"Existing Linux Launch Template: "
            f"{linux_launch_template_id}"
        )

    else:

        raise


# ============================================================
# CREATE UBUNTU LAUNCH TEMPLATE
# ============================================================

print("\n============================================================")
print("CREATING UBUNTU LAUNCH TEMPLATE")
print("============================================================")

try:

    response = ec2.create_launch_template(

        LaunchTemplateName=UBUNTU_LAUNCH_TEMPLATE_NAME,

        VersionDescription="Ubuntu Apache 8090",

        LaunchTemplateData={

            "ImageId": ubuntu_ami_id,

            "InstanceType": "t3.micro",

            "SecurityGroupIds": [
                ubuntu_sg_id
            ],

            "IamInstanceProfile": {
                "Name": SSM_INSTANCE_PROFILE
            },

            "UserData": base64.b64encode(
                ubuntu_user_data.encode()
            ).decode(),

            "TagSpecifications": [
                {
                    "ResourceType": "instance",

                    "Tags": [
                        {
                            "Key": "Name",
                            "Value": "Ubuntu-ASG-Apache-8090"
                        }
                    ]
                }
            ]
        }
    )

    ubuntu_launch_template_id = response[
        "LaunchTemplate"
    ]["LaunchTemplateId"]

    print(
        f"Ubuntu Launch Template created: "
        f"{ubuntu_launch_template_id}"
    )

except ec2.exceptions.ClientError as e:

    if "InvalidLaunchTemplateName.AlreadyExistsException" in str(e):

        print("Ubuntu Launch Template already exists.")

        response = ec2.describe_launch_templates(
            LaunchTemplateNames=[
                UBUNTU_LAUNCH_TEMPLATE_NAME
            ]
        )

        ubuntu_launch_template_id = response[
            "LaunchTemplates"
        ][0]["LaunchTemplateId"]

        print(
            f"Existing Ubuntu Launch Template: "
            f"{ubuntu_launch_template_id}"
        )

    else:

        raise


# ============================================================
# CREATE LINUX TARGET GROUP
# ============================================================

print("\n============================================================")
print("CREATING LINUX TARGET GROUP")
print("============================================================")

try:

    response = elbv2.create_target_group(

        Name=LINUX_TG_NAME,

        Protocol="HTTP",

        Port=8080,

        VpcId=VPC_ID,

        TargetType="instance",

        HealthCheckProtocol="HTTP",

        HealthCheckPort="8080",

        HealthCheckPath="/",

        HealthCheckIntervalSeconds=30,

        HealthCheckTimeoutSeconds=5,

        HealthyThresholdCount=2,

        UnhealthyThresholdCount=3,

        Matcher={
            "HttpCode": "200"
        }
    )

    linux_tg_arn = response[
        "TargetGroups"
    ][0]["TargetGroupArn"]

    print(f"Linux Target Group created: {linux_tg_arn}")

except elbv2.exceptions.DuplicateTargetGroupNameException:

    print("Linux Target Group already exists.")

    response = elbv2.describe_target_groups(
        Names=[LINUX_TG_NAME]
    )

    linux_tg_arn = response[
        "TargetGroups"
    ][0]["TargetGroupArn"]

    print(f"Existing Linux TG: {linux_tg_arn}")


# ============================================================
# CREATE UBUNTU TARGET GROUP
# ============================================================

print("\n============================================================")
print("CREATING UBUNTU TARGET GROUP")
print("============================================================")

try:

    response = elbv2.create_target_group(

        Name=UBUNTU_TG_NAME,

        Protocol="HTTP",

        Port=8090,

        VpcId=VPC_ID,

        TargetType="instance",

        HealthCheckProtocol="HTTP",

        HealthCheckPort="8090",

        HealthCheckPath="/",

        HealthCheckIntervalSeconds=30,

        HealthCheckTimeoutSeconds=5,

        HealthyThresholdCount=2,

        UnhealthyThresholdCount=3,

        Matcher={
            "HttpCode": "200"
        }
    )

    ubuntu_tg_arn = response[
        "TargetGroups"
    ][0]["TargetGroupArn"]

    print(f"Ubuntu Target Group created: {ubuntu_tg_arn}")

except elbv2.exceptions.DuplicateTargetGroupNameException:

    print("Ubuntu Target Group already exists.")

    response = elbv2.describe_target_groups(
        Names=[UBUNTU_TG_NAME]
    )

    ubuntu_tg_arn = response[
        "TargetGroups"
    ][0]["TargetGroupArn"]

    print(f"Existing Ubuntu TG: {ubuntu_tg_arn}")


# ============================================================
# CREATE APPLICATION LOAD BALANCER
# ============================================================

print("\n============================================================")
print("CREATING APPLICATION LOAD BALANCER")
print("============================================================")

try:

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

    alb_arn = response[
        "LoadBalancers"
    ][0]["LoadBalancerArn"]

    alb_dns = response[
        "LoadBalancers"
    ][0]["DNSName"]

    print(f"ALB created: {alb_arn}")
    print(f"ALB DNS: {alb_dns}")

except elbv2.exceptions.DuplicateLoadBalancerNameException:

    print("ALB already exists.")

    response = elbv2.describe_load_balancers(
        Names=[ALB_NAME]
    )

    alb_arn = response[
        "LoadBalancers"
    ][0]["LoadBalancerArn"]

    alb_dns = response[
        "LoadBalancers"
    ][0]["DNSName"]

    print(f"Existing ALB: {alb_arn}")
    print(f"ALB DNS: {alb_dns}")


# ============================================================
# WAIT FOR ALB
# ============================================================

print("\nWaiting for ALB to become active...")

while True:

    response = elbv2.describe_load_balancers(
        LoadBalancerArns=[alb_arn]
    )

    state = response[
        "LoadBalancers"
    ][0]["State"]["Code"]

    print(f"ALB state: {state}")

    if state == "active":
        break

    time.sleep(10)


print("ALB is active.")


# ============================================================
# CREATE LINUX LISTENER - PORT 8080
# ============================================================

print("\n============================================================")
print("CREATING LINUX LISTENER")
print("============================================================")

try:

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

    linux_listener_arn = response[
        "Listeners"
    ][0]["ListenerArn"]

    print(
        f"Linux listener created: "
        f"{linux_listener_arn}"
    )

except elbv2.exceptions.DuplicateListenerException:

    print("Linux listener already exists.")

    response = elbv2.describe_listeners(
        LoadBalancerArn=alb_arn
    )

    linux_listener_arn = None

    for listener in response["Listeners"]:

        if listener["Port"] == 8080:

            linux_listener_arn = listener["ListenerArn"]

            break

    print(
        f"Existing Linux listener: "
        f"{linux_listener_arn}"
    )


# ============================================================
# CREATE UBUNTU LISTENER - PORT 8090
# ============================================================

print("\n============================================================")
print("CREATING UBUNTU LISTENER")
print("============================================================")

try:

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

    ubuntu_listener_arn = response[
        "Listeners"
    ][0]["ListenerArn"]

    print(
        f"Ubuntu listener created: "
        f"{ubuntu_listener_arn}"
    )

except elbv2.exceptions.DuplicateListenerException:

    print("Ubuntu listener already exists.")

    response = elbv2.describe_listeners(
        LoadBalancerArn=alb_arn
    )

    ubuntu_listener_arn = None

    for listener in response["Listeners"]:

        if listener["Port"] == 8090:

            ubuntu_listener_arn = listener["ListenerArn"]

            break

    print(
        f"Existing Ubuntu listener: "
        f"{ubuntu_listener_arn}"
    )


# ============================================================
# ALB SG -> LINUX SG
# ============================================================

print("\n============================================================")
print("ALLOWING ALB -> LINUX INSTANCE PORT 8080")
print("============================================================")

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

    print("ALB -> Linux 8080 rule added.")

except ec2.exceptions.ClientError as e:

    if "InvalidPermission.Duplicate" in str(e):

        print("ALB -> Linux 8080 rule already exists.")

    else:

        raise


# ============================================================
# ALB SG -> UBUNTU SG
# ============================================================

print("\n============================================================")
print("ALLOWING ALB -> UBUNTU INSTANCE PORT 8090")
print("============================================================")

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

    print("ALB -> Ubuntu 8090 rule added.")

except ec2.exceptions.ClientError as e:

    if "InvalidPermission.Duplicate" in str(e):

        print("ALB -> Ubuntu 8090 rule already exists.")

    else:

        raise


# ============================================================
# CREATE LINUX AUTO SCALING GROUP
# ============================================================

print("\n============================================================")
print("CREATING LINUX AUTO SCALING GROUP")
print("============================================================")

try:

    autoscaling.create_auto_scaling_group(

        AutoScalingGroupName=LINUX_ASG_NAME,

        LaunchTemplate={
            "LaunchTemplateId": linux_launch_template_id,
            "Version": "$Latest"
        },

        MinSize=1,

        DesiredCapacity=1,

        MaxSize=2,

        VPCZoneIdentifier=PRIVATE_SUBNET_ID,

        TargetGroupARNs=[
            linux_tg_arn
        ],

        HealthCheckType="ELB",

        HealthCheckGracePeriod=180,

        Tags=[
            {
                "Key": "Name",
                "Value": "Linux-ASG-Apache-8080",
                "PropagateAtLaunch": True
            }
        ]
    )

    print("Linux ASG created.")

except autoscaling.exceptions.AlreadyExistsFault:

    print("Linux ASG already exists.")


# ============================================================
# CREATE UBUNTU AUTO SCALING GROUP
# ============================================================

print("\n============================================================")
print("CREATING UBUNTU AUTO SCALING GROUP")
print("============================================================")

try:

    autoscaling.create_auto_scaling_group(

        AutoScalingGroupName=UBUNTU_ASG_NAME,

        LaunchTemplate={
            "LaunchTemplateId": ubuntu_launch_template_id,
            "Version": "$Latest"
        },

        MinSize=1,

        DesiredCapacity=1,

        MaxSize=2,

        VPCZoneIdentifier=PRIVATE_SUBNET_ID,

        TargetGroupARNs=[
            ubuntu_tg_arn
        ],

        HealthCheckType="ELB",

        HealthCheckGracePeriod=180,

        Tags=[
            {
                "Key": "Name",
                "Value": "Ubuntu-ASG-Apache-8090",
                "PropagateAtLaunch": True
            }
        ]
    )

    print("Ubuntu ASG created.")

except autoscaling.exceptions.AlreadyExistsFault:

    print("Ubuntu ASG already exists.")


# ============================================================
# LINUX CPU AUTO SCALING POLICY
# ============================================================

print("\n============================================================")
print("CREATING LINUX CPU SCALING POLICY")
print("============================================================")

try:

    autoscaling.put_scaling_policy(

        AutoScalingGroupName=LINUX_ASG_NAME,

        PolicyName="linux-cpu-target-50",

        PolicyType="TargetTrackingScaling",

        TargetTrackingConfiguration={

            "PredefinedMetricSpecification": {

                "PredefinedMetricType":
                    "ASGAverageCPUUtilization"
            },

            "TargetValue": 50.0,

            "DisableScaleIn": False
        }
    )

    print("Linux CPU scaling policy created.")

except Exception as e:

    print(f"Linux scaling policy message: {e}")


# ============================================================
# UBUNTU CPU AUTO SCALING POLICY
# ============================================================

print("\n============================================================")
print("CREATING UBUNTU CPU SCALING POLICY")
print("============================================================")

try:

    autoscaling.put_scaling_policy(

        AutoScalingGroupName=UBUNTU_ASG_NAME,

        PolicyName="ubuntu-cpu-target-50",

        PolicyType="TargetTrackingScaling",

        TargetTrackingConfiguration={

            "PredefinedMetricSpecification": {

                "PredefinedMetricType":
                    "ASGAverageCPUUtilization"
            },

            "TargetValue": 50.0,

            "DisableScaleIn": False
        }
    )

    print("Ubuntu CPU scaling policy created.")

except Exception as e:

    print(f"Ubuntu scaling policy message: {e}")


# ============================================================
# WAIT FOR ASG INSTANCES
# ============================================================

print("\n============================================================")
print("WAITING FOR ASG INSTANCES")
print("============================================================")

print("\nWaiting for Linux ASG instance...")

for i in range(30):

    response = autoscaling.describe_auto_scaling_groups(

        AutoScalingGroupNames=[
            LINUX_ASG_NAME
        ]
    )

    groups = response["AutoScalingGroups"]

    if groups:

        instances = groups[0]["Instances"]

        if instances:

            for instance in instances:

                print(
                    f"Linux instance: "
                    f"{instance['InstanceId']} "
                    f"State: {instance['LifecycleState']} "
                    f"Health: {instance['HealthStatus']}"
                )

            if any(
                instance["LifecycleState"] == "InService"
                for instance in instances
            ):

                break

    time.sleep(10)


print("\nWaiting for Ubuntu ASG instance...")

for i in range(30):

    response = autoscaling.describe_auto_scaling_groups(

        AutoScalingGroupNames=[
            UBUNTU_ASG_NAME
        ]
    )

    groups = response["AutoScalingGroups"]

    if groups:

        instances = groups[0]["Instances"]

        if instances:

            for instance in instances:

                print(
                    f"Ubuntu instance: "
                    f"{instance['InstanceId']} "
                    f"State: {instance['LifecycleState']} "
                    f"Health: {instance['HealthStatus']}"
                )

            if any(
                instance["LifecycleState"] == "InService"
                for instance in instances
            ):

                break

    time.sleep(10)


# ============================================================
# WAIT FOR TARGET HEALTH
# ============================================================

print("\n============================================================")
print("WAITING FOR LOAD BALANCER HEALTH CHECKS")
print("============================================================")


def wait_for_healthy_target(target_group_arn, target_group_name):

    print(
        f"\nChecking targets for {target_group_name}..."
    )

    for attempt in range(30):

        try:

            response = elbv2.describe_target_health(

                TargetGroupArn=target_group_arn
            )

            descriptions = response[
                "TargetHealthDescriptions"
            ]

            if descriptions:

                all_healthy = True

                for target in descriptions:

                    target_id = target[
                        "Target"]["Id"
                    ]

                    state = target[
                        "TargetHealth"
                    ]["State"]

                    print(
                        f"{target_group_name} | "
                        f"{target_id} | "
                        f"{state}"
                    )

                    if state != "healthy":

                        all_healthy = False

                if all_healthy:

                    print(
                        f"{target_group_name} "
                        f"is healthy."
                    )

                    return

        except Exception as e:

            print(
                f"Health check waiting: {e}"
            )

        time.sleep(10)

    print(
        f"Timeout waiting for "
        f"{target_group_name}."
    )


wait_for_healthy_target(
    linux_tg_arn,
    LINUX_TG_NAME
)

wait_for_healthy_target(
    ubuntu_tg_arn,
    UBUNTU_TG_NAME
)


# ============================================================
# DISPLAY ASG INFORMATION
# ============================================================

print("\n============================================================")
print("FINAL ASG INFORMATION")
print("============================================================")


linux_asg = autoscaling.describe_auto_scaling_groups(
    AutoScalingGroupNames=[
        LINUX_ASG_NAME
    ]
)["AutoScalingGroups"][0]


ubuntu_asg = autoscaling.describe_auto_scaling_groups(
    AutoScalingGroupNames=[
        UBUNTU_ASG_NAME
    ]
)["AutoScalingGroups"][0]


print("\nLinux ASG")
print("--------------------------------------------")
print(f"Name: {LINUX_ASG_NAME}")
print(f"Min: {linux_asg['MinSize']}")
print(f"Desired: {linux_asg['DesiredCapacity']}")
print(f"Max: {linux_asg['MaxSize']}")

for instance in linux_asg["Instances"]:

    print(
        f"Instance: {instance['InstanceId']} | "
        f"State: {instance['LifecycleState']} | "
        f"Health: {instance['HealthStatus']}"
    )


print("\nUbuntu ASG")
print("--------------------------------------------")
print(f"Name: {UBUNTU_ASG_NAME}")
print(f"Min: {ubuntu_asg['MinSize']}")
print(f"Desired: {ubuntu_asg['DesiredCapacity']}")
print(f"Max: {ubuntu_asg['MaxSize']}")

for instance in ubuntu_asg["Instances"]:

    print(
        f"Instance: {instance['InstanceId']} | "
        f"State: {instance['LifecycleState']} | "
        f"Health: {instance['HealthStatus']}"
    )


# ============================================================
# FINAL OUTPUT
# ============================================================

print("\n============================================================")
print("DEPLOYMENT COMPLETE")
print("============================================================")

print("\nApplication Load Balancer:")
print(alb_dns)

print("\nLinux application:")
print(
    f"http://{alb_dns}:8080"
)

print("\nUbuntu application:")
print(
    f"http://{alb_dns}:8090"
)

print("\nArchitecture:")
print("ALB")
print("  |-- :8080 --> Linux Target Group --> Linux ASG")
print("  |-- :8090 --> Ubuntu Target Group --> Ubuntu ASG")

print("\nLinux:")
print("  Launch Template -> Amazon Linux 2023")
print("  Apache -> Port 8080")
print("  ASG -> 1 minimum / 1 desired / 2 maximum")

print("\nUbuntu:")
print("  Launch Template -> Ubuntu 24.04")
print("  Apache -> Port 8090")
print("  ASG -> 1 minimum / 1 desired / 2 maximum")

print("\nCPU scaling:")
print("  Target CPU: 50%")

