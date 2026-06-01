## Python Virtual Environment Creation:

1. python3 -m venv path/to/venv
2. source path/to/venv/bin/activate
3. python3 -m pip install xyz

## Anytime you use to virtual environment:

Run source path/to/venv/bin/activate
Then run the python execution
After compelted Run: deactivate

## Architecture Build Order

![Architecture Build Order](images/architecture-build-order.png)

<h2>Architecture Build Order</h2>

<p align="center">
  <img src="images/architecture-build-order.png" alt="Architecture Build Order" width="800">
</p>

# Steps for this demo:

## Step 1: Prerequisites

1. An AWS account. Pick one region and stay in it the whole time.
2. A GitHub account and an empty public repo, e.g. flask-cicd-demo.
3. An EC2 key pair (Console → EC2 → Key Pairs → Create key pair → .pem). We will use this one in the coming steps to SSH into the Jenkins server.
4. Your own public IP for locking down SSH/Jenkins access. Get it from "curl -4 ifconfig.me" — you'll use it as YOUR.IP/32 for configuring Security Group in AWS.

## Step 2: Build the VPC and networking (do this first)

Everything sits inside this VPC.  we will do each piece manually.

### 2.1 Create the VPC

VPC → Your VPCs → Create VPC
Choose VPC only
Name tag: flask-vpc
IPv4 CIDR: 10.0.0.0/16
Leave IPv6 off, tenancy default → Create VPC

### 2.2 Enable DNS (needed for public hostnames + SSM)

Select flask-vpc → Actions → Edit VPC settings
Tick Enable DNS resolution and Enable DNS hostnames → Save

### 2.3 Create two public subnets (two AZs — the ALB requires it)

VPC → Subnets → Create subnet → VPC = flask-vpc
Subnet 1: name flask-public-a, AZ ap-south-1a, CIDR 10.0.1.0/24
Subnet 2: name flask-public-b, AZ ap-south-1b, CIDR 10.0.2.0/24
Create both.
For each subnet: select it → Actions → Edit subnet settings →
tick Enable auto-assign public IPv4 address → Save. (This is what gives your
instances the public IPs you wanted.)

### 2.4 Create and attach an Internet Gateway

VPC → Internet gateways → Create internet gateway → name flask-igw → Create
Select it → Actions → Attach to VPC → choose flask-vpc → Attach

### 2.5 Create a public route table and add the internet route

VPC → Route tables → Create route table → name flask-public-rt,
VPC = flask-vpc → Create
Select flask-public-rt → Routes tab → Edit routes → Add route:

Destination 0.0.0.0/0 → Target Internet Gateway → flask-igw → Save

Subnet associations tab → Edit subnet associations → tick both
flask-public-a and flask-public-b → Save



That's the whole network: a /16 VPC, two public subnets in two AZs, an IGW, and a route
table sending 0.0.0.0/0 to the IGW. Because outbound goes straight to the IGW, your
instances can reach GitHub, dnf, and the SSM endpoints with no NAT Gateway needed.

Why two subnets? An Application Load Balancer must sit in at least two Availability
Zones. The ASG will also spread instances across both for resilience.

## Step 3: The application code (push this to GitHub)

1. app.py
2. requirements.txt
3. test_app.py
4. JenkinsFile

All of these are available in my current repo.

## Step 4: Security Groups

Create three, all in flask-vpc (be sure to pick your VPC, not the default):
NameInbound rulessg-jenkinsSSH (22) from YOUR.IP/32; Custom TCP 8080 from YOUR.IP/32sg-albHTTP (80) from 0.0.0.0/0sg-appCustom TCP 5000 from sg-alb (source = the ALB SG); plus Custom TCP 5000 from YOUR.IP/32 (for direct testing); SSH (22) from YOUR.IP/32 (optional)
Leave outbound as default (all allowed) on all three.

Tip: For the sg-app port-5000 rule, set the source to the security group sg-alb,
not an IP range. That's what lets only the load balancer reach your instances.

## Step 5: IAM roles (IAM → Roles → Create role)

### Role A — `app-instance-role`

This role will be attached to the application EC2 instances and allows AWS Systems Manager (SSM) access.

#### Step A.1: Select Trusted Entity

1. Navigate to **IAM → Roles → Create role**
2. Select:

   * **Trusted entity type:** AWS service
   * **Use case:** EC2

     * Select the standard **EC2** option:

       > Allow EC2 instances to call AWS services on your behalf
3. Click **Next**

#### Step A.2: Add Permissions

1. Search for:

   ```text
   AmazonSSMManagedInstanceCore
   ```

2. Select the checkbox.

3. Click **Next**.

#### Step A.3: Name and Create

1. Role name:

   ```text
   app-instance-role
   ```

2. Review the configuration.

3. Verify the trust policy contains:

   ```json
   {
     "Service": "ec2.amazonaws.com"
   }
   ```

4. Click **Create role**.


---

### Role B — `jenkins-role`

This role will be attached to the Jenkins EC2 instance and allows Jenkins to interact with AWS Systems Manager and discover EC2 instances.

#### Step B.1: Select Trusted Entity

1. Navigate to **IAM → Roles → Create role**
2. Select:

   * **Trusted entity type:** AWS service
   * **Use case:** EC2
3. Click **Next**

#### Step B.2: Add Permissions

1. Search for:

   ```text
   AmazonSSMManagedInstanceCore
   ```

2. Select the checkbox.

3. Click **Next**

> This permission is optional but recommended because it allows SSM access to the Jenkins instance.

#### Step B.3: Name and Create

1. Role name:

   ```text
   jenkins-role
   ```

2. Click **Create role**

---

### Add Inline Policy to `jenkins-role`

After the role is created:

1. Navigate to:

   ```text
   IAM → Roles → jenkins-role
   ```

2. Open the **Permissions** tab.

3. Click:

   ```text
   Add permissions → Create inline policy
   ```

4. Select the **JSON** tab.

5. Remove the default content.

6. Paste the following policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:SendCommand",
        "ssm:GetCommandInvocation",
        "ssm:ListCommandInvocations",
        "ssm:ListCommands"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances"
      ],
      "Resource": "*"
    }
  ]
}
```

7. Click **Review policy**

8. Policy name:

   ```text
   Jenkins-SSM-EC2-Access
   ```

9. Click **Create policy**

---

## Step 6: Security Groups

Create the following security groups in **flask-vpc**:

### `jenkins-sg`

**Inbound Rules**

* SSH (22) → YOUR.IP/32
* Custom TCP (8080) → YOUR.IP/32

**Outbound**

* Allow all (default)

---

### `alb-sg`

**Inbound Rules**

* HTTP (80) → 0.0.0.0/0

**Outbound**

* Allow all (default)

---

### `app-sg`

**Inbound Rules**

* Custom TCP (5000) → Source: `alb-sg`
* Custom TCP (5000) → YOUR.IP/32 (for testing)
* SSH (22) → YOUR.IP/32 (optional)

**Outbound**

* Allow all (default)

> **Important:** For port **5000**, use **`alb-sg`** as the source security group, not an IP range. This ensures only the Load Balancer can access the application instances.

## Step 7: Launch the Jenkins instance


Navigate to **EC2 → Launch Instance** and configure the following:

| Setting               | Value                            |
| --------------------- | -------------------------------- |
| Name                  | `jenkins-server`                 |
| AMI                   | Amazon Linux 2023                |
| Instance Type         | `t3.micro`                       |
| Key Pair              | Use the key pair created earlier |
| VPC                   | `flask-vpc`                      |
| Subnet                | `flask-public-a`                 |
| Auto-assign Public IP | Enable                           |
| Security Group        | `jenkins-sg`                     |
| IAM Instance Profile  | `jenkins-role`                   |

### User Data

Under **Advanced Details → User Data**, paste the contents of:

```text
jenkins_install_script_on_ec2
```

from the GitHub repository.

Click **Launch Instance**.

---

### Verify Jenkins Installation

Wait a few minutes for the EC2 User Data script to complete.

Once the instance is up, SSH into the instance:

```bash
cd <path-to-your-pem-file>

ssh -i your-key.pem ec2-user@<jenkins-public-ip>
```

---

### Retrieve Jenkins Initial Admin Password

After logging in, run:

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

Copy the generated password.

---

### Access Jenkins

Open your browser:

```text
http://<jenkins-public-ip>:8080
```

Paste the initial admin password and continue with the Jenkins setup wizard.

## Step 8: Configure Jenkins

1. Open Jenkins in your browser:

```text
http://<jenkins-public-ip>:8080
```

2. Paste the **initial admin password** retrieved earlier.

3. Select:

```text
Install Suggested Plugins
```

4. Create your Jenkins admin user and complete the setup wizard.

---

### Verify AWS Access

Since the EC2 instance is using the **jenkins-role** IAM role, no AWS credentials need to be configured manually.

SSH into the Jenkins instance and run:

```bash
sudo -u jenkins aws sts get-caller-identity --region ap-south-1
```

Expected output:

```json
{
  "UserId": "...",
  "Account": "...",
  "Arn": "arn:aws:sts::123456789012:assumed-role/jenkins-role/..."
}
```

The ARN should contain:

```text
jenkins-role
```

If the command fails, verify:

* The EC2 instance has the **jenkins-role** attached.
* The role contains the required permissions.
* The AWS CLI is installed on the Jenkins instance.


## Step 9: Create Launch Template for Application Servers

Navigate to **EC2 → Launch Templates → Create Launch Template** and configure:

| Setting              | Value                              |
| -------------------- | ---------------------------------- |
| Name                 | `flask-app-lt`                     |
| AMI                  | Amazon Linux 2023                  |
| Instance Type        | `t3.micro`                         |
| Key Pair             | Optional (SSM access is available) |
| Security Group       | `app-sg`                           |
| IAM Instance Profile | `app-instance-role`                |

### User Data

Replace `<YOUR_USER>` with your GitHub username and paste the following:

```bash
#!/bin/bash
set -euxo pipefail
exec > /var/log/user-data.log 2>&1

dnf update -y
dnf install -y python3 python3-pip git

useradd -m appuser 2>/dev/null || true
rm -rf /home/appuser/app
git clone https://github.com/sahilsahu246/python-flask-demo.git /home/appuser/app
chown -R appuser:appuser /home/appuser/app
cd /home/appuser/app

pip3 install -r requirements.txt
pip3 install gunicorn

cat > /etc/systemd/system/flaskapp.service <<'EOF'
[Unit]
Description=Flask App
After=network-online.target
Wants=network-online.target

[Service]
User=appuser
WorkingDirectory=/home/appuser/app
ExecStart=/usr/bin/python3 -m gunicorn -w 2 -b 0.0.0.0:5000 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now flaskapp
```

### Notes

* Do **not** specify a VPC or subnet in the Launch Template.
* Do **not** add tags in the Launch Template.
* The Auto Scaling Group will control subnet placement.
* The `Role=flask-app` tag will be added in the Auto Scaling Group and propagated to all instances.
* Jenkins will use this tag to identify deployment targets.


