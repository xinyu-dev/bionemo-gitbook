# Launch container on AWS EC2

## Prerequisites

{% hint style="info" %}
`org`, `team` is only important when you are pulling private containers/datasets from NGC that you or your team created. `ace` does not matter here - just choose any from the options provided by the prompt. 
{% endhint %}

## Steps

### Step 1: Launch an EC2 instance
1. In [AWS EC2 console](https://us-east-1.console.aws.amazon.com/ec2/home?region=us-east-1), click on **Launch Instance**. This will open a instance specification page. 
    <figure><img src="../.gitbook/assets/images/ec2-launch-instance.jpg" alt=""><figcaption><p>Launch Instance</p></figcaption></figure>
2. **Name**: enter a name for your instance
   <figure><img src="../.gitbook/assets/images/ec2-name-instance.jpg" alt=""><figcaption><p>Name Instance</p></figcaption></figure>
3. Under **Application & OS Images**:
   - select **Browse more AMIs**.
        <figure><img src="../.gitbook/assets/images/ec2-browse-ami.jpg" alt=""><figcaption><p>Browse AMIs</p></figcaption></figure>
   - Type `nvidia` in the search bar. Press `Enter`. Then click on **AWS Marketplace AMI**. Then select **NVIDIA GPU Optimized VMI** and click on **Select**.
         <figure><img src="../.gitbook/assets/images/ec2-choose-ami.jpg" alt=""><figcaption><p>choose AMI</p></figcaption></figure>
   - When prompted, select **Subscribe Now**
4. Under **instance type**, select **p3dn.24xlarge**.
   <figure><img src="../.gitbook/assets/images/ec2-choose-instance.jpg" alt=""><figcaption><p>choose instance</p></figcaption></figure>
5. Under **key pair**: Choose an existing key pair or create a new one. If you create a new one, enter a keypair name, then select **RSA** and **.pem**. Download the **.pem** file for later use. 
   <figure><img src="../.gitbook/assets/images/ec2-keypairs.jpg" alt=""><figcaption><p>choose key pair</p></figcaption></figure>
6. Under **Network settings**: choose the network, subnet, and security group that you want to use. An example is shown below but should be modified according to your organization's policies.
   <figure><img src="../.gitbook/assets/images/ec2-network-settings.jpg" alt=""><figcaption><p>choose network</p></figcaption></figure>
7. Keep other settings default (or change them as needed). At least 124G root EBS volume is recommended as shown in the default setting for pretrained models & datasets.
8. Click on **Launch Instance**. Wait until the `Instance State` becomes `running`.


### Step 2. Connect to a running instance
1. In the EC2 console, wait until the instance state becomes `running`. Then copy the **Public IP4 address** or **Private IP4 address** of the instance, depending on your network settings. 
    <figure><img src="../.gitbook/assets/images/ec2-copy-ip.jpg" alt=""><figcaption><p>copy IP</p></figcaption></figure>
2. Open a terminal at the local folder where you keep the **.pem** file that was used during instance launch.  Run the following command to change the permissions of the **.pem** file. Replace `your-key-pair.pem` with the name of your **.pem** file.
    ```shell
    chmod 400 your-key-pair.pem
    ```
3. SSH into the instance.Replace `your-ip4-address` with the public or private IP4 address of your instance. 
    ```shell
    ssh -i your-key-pair.pem -L 8888:127.0.0.1:8888 ubuntu@your-ip4-address
    ```
4. The first time when you log into the instance, driver installation will start automatically. Wait until the system is ready. 

### Step 3. Pull the BioNeMo container
1. NGC CLI is preinstalled. In the ubuntu terminal, type
    ```shell
    ngc config set
    ```
2. Enter the information as prompted:  
    - `API key`: enter API key, 
    - `CLI output`: accept default (ascii) by pressing `Enter`
    - `org`: Enter the NGC org you're assigned with
    - `team`: Enter the NGC team you're assigned with
    - `ace`: Enter the `ace` and press `Enter`
9. Pull the BioNeMo container image from NGC. 
    ```shell
    docker pull nvcr.io/nvidia/clara/bionemo-framework:1.5
    ```

### Step 4. Run the BioNeMo container
1. In the ubuntu terminal, make a new folder so we can mount it to docker to persist data. Replace `xyu-workspace1` with your folder name. 
    ```shell
    cd ~ && mkdir xyu-workspace1
    ```
2. Start the container. Replace `xyu-workspace1` with your workspace name. 
    ```shell
    docker run --rm -d --gpus all -p 8888:8888 -v /home/ubuntu/xyu-workspace1:/workspace/bionemo/xyu-workspace1 nvcr.io/nvidia/clara/bionemo-framework:1.5 "jupyter lab --allow-root --ip=* --port=8888 --no-browser --NotebookApp.token='' --NotebookApp.allow_origin='*' --ContentsManager.allow_hidden=True --notebook-dir=/workspace/bionemo"
    ```
    - The `/workspace/bionemo` is the directory inside the container that contains the example and code. I prefer to use it as my home directory when working inside the container. Mount your local folders to this directory by changing the path in `-v` tag. 
3. You can now access JupyterLab by visitn `localhost:8888` in your web browser.
4. To download the pretrained model weights, open a terminal in JupyterLab. 
5. In the terminal, run the `ngc config set` again to set the NGC credentials inside the container. 
5. Then run
    ```shell
    cd /workspace/bionemo
    python download_models.py all --source ngc --download_dir ${BIONEMO_HOME}/models --verbose
    ```
    This will create download the models to `/workspace/bionemo/models` folder. 
6. Optionally, persist the models by copying them to your workspace
    ```shell
    mkdir -p xyu-workspace1/bionemo && cp -r models xyu-workspace1/bionemo/models
    ```
Next time, when you launch the container, you can mount the `models` folder to the container under the `/workspace/bionemo` directory.
7. The final directory structure should look like this:
    <figure><img src="../.gitbook/assets/images/ngc-jupyterlab.jpg" alt=""><figcaption><p>ngc-jupyterlab</p></figcaption></figure>




## Notes
### Choice of instance type. 
We test BioNeMo on A100, but usually V100 and A10 can also be used. 
### Volume 
Instead of creating a local folder on EBS, you can also mount [EFS](https://aws.amazon.com/efs/) or [Lustre](https://aws.amazon.com/fsx/lustre/) folders to share across EC2 instances

