import boto3
import time
import json


# ============================================================
# CONFIGURATION
# ============================================================

PROFILE = "sravana_test"
REGION = "eu-west-2"

# ------------------------------------------------------------
# Existing VPC / PRIVATE SUBNET
# ------------------------------------------------------------

VPC_ID = "vpc-084dc161e5a0846db"

PRIVATE_SUBNET_ID = "subnet-0d77a90195a2525e7"

# ------------------------------------------------------------
# EC2 configuration
# ------------------------------------------------------------

INSTANCE_TYPE = "t3.micro"

INSTANCE_NAME = "Windows-Apache-8070"

SECURITY_GROUP_NAME = "Windows-apache-sg"

APACHE_PORT = 8070

# ------------------------------------------------------------
# IAM names
# ------------------------------------------------------------

IAM_ROLE_NAME = "WindowsEC2SSMRole"

INSTANCE_PROFILE_NAME = "WindowsEC2SSMInstanceProfile"


# ============================================================
# AWS SESSION
# ============================================================

session = boto3.Session(
    profile_name=PROFILE,
    region_name=REGION
)

ec2 = session.client("ec2")
iam = session.client("iam")
ssm = session.client("ssm")


# ============================================================
# FIND LATEST WINDOWS SERVER 2025 AMI
# ============================================================

print("\nFinding latest Windows Server 2025 AMI...")

ami_response = ec2.describe_images(

    Owners=["amazon"],

    Filters=[

        {
            "Name": "name",
            "Values": [
                "Windows_Server-2025-English-Full-Base-*"
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
        }
    ]
)

images = sorted(
    ami_response["Images"],
    key=lambda x: x["CreationDate"],
    reverse=True
)

if not images:
    raise Exception(
        "No Windows Server 2025 AMI found in this region."
    )

AMI_ID = images[0]["ImageId"]

AMI_NAME = images[0]["Name"]

print(f"Windows AMI found:")
print(f"AMI ID   : {AMI_ID}")
print(f"AMI Name : {AMI_NAME}")


# ============================================================
# CREATE IAM ROLE FOR SSM
# ============================================================

print("\nChecking IAM role...")

assume_role_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "ec2.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}

try:

    iam.get_role(
        RoleName=IAM_ROLE_NAME
    )

    print(
        f"IAM role already exists: {IAM_ROLE_NAME}"
    )

except iam.exceptions.NoSuchEntityException:

    print("IAM role does not exist. Creating it...")

    iam.create_role(

        RoleName=IAM_ROLE_NAME,

        AssumeRolePolicyDocument=json.dumps(
            assume_role_policy
        ),

        Description=(
            "IAM role for Windows EC2 "
            "with AWS Systems Manager access"
        )
    )

    print(
        f"IAM role created: {IAM_ROLE_NAME}"
    )

    # Give IAM time to propagate
    time.sleep(5)


# ============================================================
# ATTACH SSM POLICY
# ============================================================

print("\nAttaching AmazonSSMManagedInstanceCore...")

iam.attach_role_policy(

    RoleName=IAM_ROLE_NAME,

    PolicyArn=(
        "arn:aws:iam::aws:policy/"
        "AmazonSSMManagedInstanceCore"
    )
)

print(
    "AmazonSSMManagedInstanceCore attached."
)

# ============================================================
# CREATE INSTANCE PROFILE
# ============================================================

print("\nChecking instance profile...")


try:

    iam.get_instance_profile(
        InstanceProfileName=INSTANCE_PROFILE_NAME
    )

    print(
        f"Instance profile already exists: "
        f"{INSTANCE_PROFILE_NAME}"
    )

except iam.exceptions.NoSuchEntityException:

    print("Creating instance profile...")

    iam.create_instance_profile(

        InstanceProfileName=INSTANCE_PROFILE_NAME
    )

    print("Instance profile created.")

    # Give IAM a moment
    time.sleep(5)

    iam.add_role_to_instance_profile(

        InstanceProfileName=INSTANCE_PROFILE_NAME,

        RoleName=IAM_ROLE_NAME
    )

    print("IAM role added to instance profile.")

    time.sleep(5)


# ============================================================
# CREATE SECURITY GROUP
# ============================================================

print("\nChecking security group...")


try:

    response = ec2.describe_security_groups(

        Filters=[

            {
                "Name": "group-name",
                "Values": [
                    SECURITY_GROUP_NAME
                ]
            },

            {
                "Name": "vpc-id",
                "Values": [
                    VPC_ID
                ]
            }
        ]
    )

    if response["SecurityGroups"]:

        SECURITY_GROUP_ID = (
            response["SecurityGroups"][0]["GroupId"]
        )

        print(
            f"Using existing security group: "
            f"{SECURITY_GROUP_ID}"
        )

    else:

        raise Exception(
            "Security group lookup failed."
        )


except Exception:

    print("Creating security group...")

    response = ec2.create_security_group(

        GroupName=SECURITY_GROUP_NAME,

        Description=(
            "Windows Apache server "
            "managed through SSM"
        ),

        VpcId=VPC_ID
    )

    SECURITY_GROUP_ID = response["GroupId"]

    print(
        f"Security group created: "
        f"{SECURITY_GROUP_ID}"
    )


# ============================================================
# SECURITY GROUP
# ============================================================

print("\nConfiguring security group...")

print(
    "No inbound rules are required for SSM."
)

# We intentionally DO NOT add:
#
# 3389 RDP
# 8070 Apache
#
# because the instance is private and
# we are using SSM.


USER_DATA = r'''
<powershell>

$ErrorActionPreference = "Stop"

# ============================================================
# CONFIGURATION
# ============================================================

$ApacheUrl = "https://www.apachelounge.com/download/VS18/binaries/httpd-2.4.69-261002-Win64-VS18.zip"

$ApacheZip = "C:\apache.zip"

$ApacheHome = "C:\Apache24"

$ApacheConfig = "$ApacheHome\conf\httpd.conf"

$ApachePort = 8070

$LogFile = "C:\windows-apache-bootstrap.log"


# ============================================================
# START LOGGING
# ============================================================

Start-Transcript -Path $LogFile -Append

Write-Host "=========================================="
Write-Host "Windows Apache Bootstrap Started"
Write-Host "=========================================="


# ============================================================
# DOWNLOAD APACHE
# ============================================================

Write-Host "Downloading Apache..."

curl.exe -L $ApacheUrl -o $ApacheZip

if (-not (Test-Path $ApacheZip)) {
    throw "Apache ZIP download failed."
}

$ZipSize = (Get-Item $ApacheZip).Length

Write-Host "Apache ZIP size: $ZipSize bytes"

if ($ZipSize -lt 10000000) {
    throw "Apache ZIP appears to be invalid or incomplete."
}


# ============================================================
# EXTRACT APACHE
# ============================================================

Write-Host "Extracting Apache..."

if (Test-Path $ApacheHome) {
    Remove-Item $ApacheHome -Recurse -Force
}

Expand-Archive `
    -Path $ApacheZip `
    -DestinationPath "C:\" `
    -Force


# ============================================================
# VERIFY APACHE
# ============================================================

if (-not (Test-Path "$ApacheHome\bin\httpd.exe")) {
    throw "Apache executable was not found."
}

Write-Host "Apache extracted successfully."


# ============================================================
# CONFIGURE APACHE PORT 8070
# ============================================================

Write-Host "Configuring Apache port $ApachePort..."

$configContent = Get-Content $ApacheConfig

$configContent = $configContent -replace `
    '^Listen 80$', `
    "Listen $ApachePort"

$configContent | Set-Content $ApacheConfig


# ============================================================
# ADD SERVER NAME
# ============================================================

Add-Content $ApacheConfig "`nServerName localhost:$ApachePort"


# ============================================================
# CREATE INDEX.HTML
# ============================================================

Write-Host "Creating index.html..."

@"
"This is a Windows Server on port 8070" |
"@ | Set-Content "$ApacheHome\htdocs\index.html"


# ============================================================
# TEST APACHE CONFIGURATION
# ============================================================

Write-Host "Testing Apache configuration..."

& "$ApacheHome\bin\httpd.exe" -t

if ($LASTEXITCODE -ne 0) {
    throw "Apache configuration test failed."
}

Write-Host "Apache configuration: OK"


# ============================================================
# INSTALL APACHE AS WINDOWS SERVICE
# ============================================================

Write-Host "Installing Apache Windows service..."

& "$ApacheHome\bin\httpd.exe" -k install

Start-Sleep -Seconds 3


# ============================================================
# START APACHE SERVICE
# ============================================================

Write-Host "Starting Apache service..."

Start-Service Apache2.4

Start-Sleep -Seconds 5


# ============================================================
# VERIFY SERVICE
# ============================================================

$ApacheService = Get-Service Apache2.4

if ($ApacheService.Status -ne "Running") {
    throw "Apache service failed to start."
}

Write-Host "Apache service is RUNNING."


# ============================================================
# WINDOWS FIREWALL
# ============================================================

Write-Host "Creating Windows Firewall rule for port 8070..."

if (-not (Get-NetFirewallRule `
    -DisplayName "Apache HTTP 8070" `
    -ErrorAction SilentlyContinue)) {

    New-NetFirewallRule `
        -DisplayName "Apache HTTP 8070" `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $ApachePort `
        -Action Allow
}


# ============================================================
# TEST APACHE
# ============================================================

Write-Host "Testing Apache HTTP endpoint..."

Start-Sleep -Seconds 3

$response = Invoke-WebRequest `
    -Uri "http://localhost:$ApachePort" `
    -UseBasicParsing

if ($response.StatusCode -ne 200) {
    throw "Apache HTTP test failed."
}

Write-Host "Apache HTTP test successful."

Write-Host "HTTP Status: $($response.StatusCode)"


# ============================================================
# VERIFY PORT
# ============================================================

Write-Host "Checking Apache port..."

netstat -ano | findstr ":$ApachePort"


# ============================================================
# CLEANUP
# ============================================================

Remove-Item $ApacheZip -Force -ErrorAction SilentlyContinue


# ============================================================
# COMPLETE
# ============================================================

Write-Host "=========================================="
Write-Host "Windows Apache Bootstrap Completed"
Write-Host "=========================================="

Stop-Transcript

</powershell>
'''


# ============================================================
# LAUNCH WINDOWS EC2
# ============================================================

print("\nLaunching Windows EC2 instance...")


response = ec2.run_instances(

    ImageId=AMI_ID,

    InstanceType=INSTANCE_TYPE,

    MinCount=1,

    MaxCount=1,

    SubnetId=PRIVATE_SUBNET_ID,

    SecurityGroupIds=[
        SECURITY_GROUP_ID
    ],

    IamInstanceProfile={
        "Name": INSTANCE_PROFILE_NAME
    },

    UserData=USER_DATA,

    TagSpecifications=[

        {
            "ResourceType": "instance",

            "Tags": [

                {
                    "Key": "Name",
                    "Value": INSTANCE_NAME
                },

                {
                    "Key": "Application",
                    "Value": "Apache"
                },

                {
                    "Key": "Port",
                    "Value": str(APACHE_PORT)
                },

                {
                    "Key": "OS",
                    "Value": "Windows"
                }
            ]
        }
    ]
)


INSTANCE_ID = (
    response["Instances"][0]["InstanceId"]
)


print("\n======================================")
print("EC2 INSTANCE CREATED")
print("======================================")

print(f"Instance ID : {INSTANCE_ID}")
print(f"AMI        : {AMI_ID}")
print(f"Instance    : {INSTANCE_TYPE}")


# ============================================================
# WAIT FOR INSTANCE
# ============================================================

print("\nWaiting for EC2 instance to start...")

waiter = ec2.get_waiter(
    "instance_running"
)

waiter.wait(
    InstanceIds=[INSTANCE_ID]
)

print("Instance is running.")


# ============================================================
# GET INSTANCE DETAILS
# ============================================================

response = ec2.describe_instances(

    InstanceIds=[
        INSTANCE_ID
    ]
)

instance = (
    response["Reservations"][0]
    ["Instances"][0]
)

PRIVATE_IP = instance.get(
    "PrivateIpAddress"
)

VPC = instance.get(
    "VpcId"
)

SUBNET = instance.get(
    "SubnetId"
)


# ============================================================
# WAIT FOR SSM
# ============================================================

print("\nWaiting for SSM registration...")

ssm_available = False

for attempt in range(30):

    try:

        response = ssm.describe_instance_information(

            Filters=[
                {
                    "Key": "InstanceIds",
                    "Values": [
                        INSTANCE_ID
                    ]
                }
            ]
        )

        if response["InstanceInformationList"]:

            ssm_available = True

            info = (
                response[
                    "InstanceInformationList"
                ][0]
            )

            print("\nSSM registration successful!")

            print(
                f"SSM Ping Status : "
                f"{info['PingStatus']}"
            )

            print(
                f"SSM Agent      : "
                f"{info['AgentVersion']}"
            )

            break

    except Exception as e:

        print(
            f"SSM check failed: {e}"
        )

    print(
        f"Waiting for SSM... "
        f"{attempt + 1}/30"
    )

    time.sleep(10)


# ============================================================
# FINAL OUTPUT
# ============================================================

print("\n")
print("============================================================")
print("WINDOWS APACHE EC2 SETUP COMPLETE")
print("============================================================")

print(f"Instance ID       : {INSTANCE_ID}")
print(f"Private IP        : {PRIVATE_IP}")
print(f"VPC               : {VPC}")
print(f"Private Subnet    : {SUBNET}")
print(f"Security Group    : {SECURITY_GROUP_ID}")
print(f"Apache Port       : {APACHE_PORT}")
print(f"SSM Ready         : {ssm_available}")

print("\n")

if ssm_available:

    print("Connect using Session Manager:")

    print(
        f"aws ssm start-session "
        f"--target {INSTANCE_ID} "
        f"--profile {PROFILE} "
        f"--region {REGION}"
    )

else:

    print(
        "SSM is not registered yet."
    )

    print(
        "Check NAT Gateway, route table, "
        "DNS and IAM configuration."
    )

print("\n============================================================")