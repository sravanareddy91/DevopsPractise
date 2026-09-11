import boto3

# AWS Configuration
PROFILE_NAME = "sravana_test"
REGION = "eu-north-1"

# Resource Configuration
VPC_ID = "vpc-0ecb0e56164812e7d"
SUBNET_ID = "subnet-0d821fe5730b71ad9"
AMI_ID = "ami-0b79f6b294a030f24"
KEY_NAME = "Test1 Keypair"
MY_IP = "151.229.116.118/32"

# AWS Session
session = boto3.Session(
    profile_name=PROFILE_NAME,
    region_name=REGION
)

# EC2 Client
ec2 = session.client("ec2")

#print("AWS session created successfully")
#print("Profile:", PROFILE_NAME)
#print("Region:", REGION)

# Create Security Group
#response = ec2.create_security_group(
    #GroupName="PractiseSG-python",
    #Description="Security group for development web server",
    #VpcId=VPC_ID
#)

#SG_ID = response["GroupId"]

#print("Security Group created successfully")
#print("Security Group ID:", SG_ID)

SG_ID = "sg-09a0e35f3bc836e01"

#print("Using existing Security Group")
#print("Security Group ID:", SG_ID)

# Add SSH inbound rule
#ec2.authorize_security_group_ingress(
    #GroupId=SG_ID,
    #IpPermissions=[
        #{
            #"IpProtocol": "tcp",
            #"FromPort": 22,
            #"ToPort": 22,
            #"IpRanges": [
             #   {
              #      "CidrIp": MY_IP,
       #             "Description": "SSH access from my IP"
      #          }
     #       ]
    #    }
   # ]
#)

#print("SSH inbound rule added successfully")

# Add HTTP inbound rule
#ec2.authorize_security_group_ingress(
 #   GroupId=SG_ID,
#    IpPermissions=[
#        {
#            "IpProtocol": "tcp",
#            "FromPort": 80,
#            "ToPort": 80,
#            "IpRanges": [
#                {
#                    "CidrIp": "0.0.0.0/0",
#                    "Description": "Allow HTTP traffic from the internet"
#                }
#            ]
#        }
#    ]
#)

#print("HTTP inbound rule added successfully")

#response = ec2.run_instances(
#    ImageId=AMI_ID,
#    InstanceType="t3.micro",
#    KeyName=KEY_NAME,
#    SecurityGroupIds=[SG_ID],
#    SubnetId=SUBNET_ID,
#    MinCount=1,
#    MaxCount=1
#)

#instance_id = response["Instances"][0]["InstanceId"]

#print("EC2 instance created successfully")
#print("Instance ID:", instance_id)
INSTANCE_ID = "i-08196dff499a0c44b"

ec2.create_tags(
    Resources=[INSTANCE_ID],
    Tags=[
        {
            "Key": "Name",
            "Value": "EC2_practise"
        },
        {
            "Key": "Resource Type",
            "Value": "EC2"
        },
        {
            "Key": "Provisioned",
            "Value": "Python"
        }
    ]
)

print("EC2 tags added successfully")

ec2.create_tags(
    Resources=[SG_ID],
    Tags=[
        {
            "Key": "Name",
            "Value": "PractiseSG-python"
        },
        {
            "Key": "Resource Type",
            "Value": "Security Group"
        },
        {
            "Key": "Provisioned",
            "Value": "python"
        }
    ]
)

print("Security Group tags added successfully")