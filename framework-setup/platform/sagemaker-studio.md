# SageMaker Studio

## Prerequisites

{% content-ref url="../configure-ngc-api-key.md" %}
[configure-ngc-api-key.md](../configure-ngc-api-key.md)
{% endcontent-ref %}

## Steps for Setting up BioNeMo Framework on SageMaker JupyterLab App

{% hint style="info" %}
This method allows you to run BioNeMo framework on SageMaker JupyterLab. The advantage of this method ist that 1) relatively simple 2) does not require converting BioNeMo functions to SageMaker functions. 3) can run on single-GPU or multi-GPU as long as it is a single node. The disadvantage is that it does not support multi-node training. For multi-node training, refer to[ this tutorial on AWS](https://github.com/aws-samples/amazon-sagemaker-with-nvidia-bionemo)
{% endhint %}

### Step 1: Build container for ECR

{% hint style="info" %}
The SageMaker JupyterLab app requires a container image at start up. Therefore we first need to create a custom BioNeMo image for ECR.&#x20;
{% endhint %}

#### Create docker file

{% hint style="danger" %}
At the time of writing there is a limit of 32G for custom image in SageMaker Studio.&#x20;
{% endhint %}

````docker
```dockerfile
FROM nvcr.io/nvidia/clara/bionemo-framework:1.7

ARG NB_USER="sagemaker-user"
ARG NB_UID=1000
ARG NB_GID=100


# Switch to root to install packages
USER root

# add user
RUN useradd --create-home --shell /bin/bash --uid ${NB_UID} --gid ${NB_GID} ${NB_USER}

# Add sudo package and add NB_USER to sudo group
# remove this step if you want to save some disk space
RUN apt-get update && apt-get install -y sudo && \
    usermod -aG sudo ${NB_USER} && \
    echo "${NB_USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Add a new group
RUN groupadd rootgroup

# Add user to the new group
RUN usermod -aG rootgroup ${NB_USER}

# Change group ownership of /root, which is required for Code Editor to work
RUN chgrp -R rootgroup /root

# Change group ownership of /workspace, so that we can modify files. 
RUN chgrp -R rootgroup /workspace

# Set group permissions
RUN chmod -R g+rwx /root
RUN chmod -R g+rwx /workspace

# bash privileges 
RUN chown ${NB_USER}:${NB_GID} /home/${NB_USER}/.bashrc

# Switch back to the non-root user
USER $NB_UID

# Reset the entrypoint, otherwise bionemo's entrypoint will be used and CMD won't run!
ENTRYPOINT []

CMD jupyter lab --ip 0.0.0.0 --port 8888 \
  --ServerApp.base_url="/jupyterlab/default" \
  --ServerApp.token='' \
  --ServerApp.allow_origin='*'
```
````

Notes:&#x20;

* The creation of `sudo` isn't necessary but does add a few GB to the image. Remove this line if needed.&#x20;
* From what I know the SageMaker team is planning to increase the limit of custom image in the future.&#x20;
* Grant root access because SageMaker JupyterLab doesn't support `UID=0` and `GID=0` (root) yet.&#x20;
* Grant access to `/worskpace` so that we can write files.
* The Amazon EBS volume for your space is mounted on the path `/home/sagemaker-user`. You can't change the mount path. We will create a symbolic link in the life cycle config file
* `ENTRYPOINT []` is a must, because the inherited container has its won definition which mess up with SageMaker.

#### Build

```bash
docker build -t <your_id>.dkr.ecr.us-east-1.amazonaws.com/bionemo-framework:1.7 .
```

Replace `your_ecr_id` with the number that comes from your ECR account.&#x20;

#### Check

1.  run container interactively,

    ```bash
    docker run -it <your_id>.dkr.ecr.us-east-1.amazonaws.com/bionemo-framework:1.7 /bin/bash
    ```
2.  check UID and GID. Should be `NB_UID=1000` and `NB_GID=100` as specified in Dockerfile.

    ```bash
    id -g
    id -u
    ```
3. Run `CMD` command block in the Dockerfile. It should work.&#x20;
4.  Run container non-interactively

    ```bash
    docker run -it <your_id>.dkr.ecr.us-east-1.amazonaws.com/bionemo-framework:1.7
    ```

    Jupyterlab server must correctly run, showing something like this:

    ```
    [I 2024-08-17 21:20:25.936 ServerApp] Serving notebooks from local directory: /workspace/bionemo
    [I 2024-08-17 21:20:25.936 ServerApp] Jupyter Server 2.14.2 is running at:
    [I 2024-08-17 21:20:25.936 ServerApp] http://hostname:8888/jupyterlab/default/lab
    [I 2024-08-17 21:20:25.936 ServerApp]     http://127.0.0.1:8888/jupyterlab/default/lab
    [I 2024-08-17 21:20:25.936 ServerApp] Use Control-C to stop this server and shut down all kernels (twice to skip confirmation).
    [W 2024-08-17 21:20:25.939 ServerApp] No web browser found: Error('could not locate runnable browser').
    ```

#### Push to ECR

1.  In ECR console, create a repository. Copy the repository URL, which looks like this:

    ```bash
    381492310382.dkr.ecr.us-east-1.amazonaws.com/bionemo-framework
    ```
2.  Run

    ```bash
    # configure aws 
    aws configure 
    # some accounts might also require aws_session_token
    aws configure set aws_session_token <token>
    ```
3.  Run

    ```bash
    aws --region us-east-1 ecr get-login-password | docker login --username AWS --password-stdin <your_id>.dkr.ecr.us-east-1.amazonaws.com/bionemo-framework
    ```
4.  push container to ECR

    ```bash
    docker push <your_id>.dkr.ecr.us-east-1.amazonaws.com/bionemo-framework:1.7
    ```
5.  Go to ECR, copy the container URI, like this:

    ```bash
    <your_id>.dkr.ecr.us-east-1.amazonaws.com/bionemo-framework:1.7    
    ```

### Attach Image to Domain

1.  Go to SageMaker console. If you do not have a SageMaker domain yet, click on **Domain** in the left bar, then create a domain using the default **Quick setup**.&#x20;

    <figure><img src="https://res.cloudinary.com/dpfqlyh21/image/upload/v1726496867/obsidian/kdycqg54uhmud8w6eybx.png" alt=""><figcaption></figcaption></figure>
2.  Click on your domain. Under the **Domain settings** tab, increase the **Storage Configurations** to maximum space size of at least 150G.&#x20;

    <figure><img src="https://res.cloudinary.com/dpfqlyh21/image/upload/v1726496956/obsidian/wi5hmycihxqgttbs5lph.png" alt=""><figcaption></figcaption></figure>
3.  Click on the **Environment** tab, find **Custom image for Studio App**&#x20;

    <figure><img src="https://res.cloudinary.com/dpfqlyh21/image/upload/v1723927631/obsidian/q2zjattggeqhxfzjkpwf.png" alt=""><figcaption></figcaption></figure>
4. Click **Attach**
5. Click **New Image**, then enter the ECR URI.
6. Go through the configs very careful. Make sure:
   * EFS mount path = `/home/sagemaker-user`
   *   `UID` and `GID` matches what you have in Dockerfile.  Select **JupyterLab Image** as the App type

       <figure><img src="https://res.cloudinary.com/dpfqlyh21/image/upload/v1723930377/obsidian/albuzklflaphs0yr6hba.png" alt=""><figcaption></figcaption></figure>
   * Select **JupyterLab Image** as the App type

### Launch JupyterLab App

1. Go to SageMaker Studio, click on **JupyterLab**
2.  Configure a space by choosing your **custom image**, like this:&#x20;

    <figure><img src="https://res.cloudinary.com/dpfqlyh21/image/upload/v1726496611/obsidian/gvqfh1y6jxrlcwdwj65g.png" alt=""><figcaption></figcaption></figure>
3. Run space
4. Once space launches, open a terminal in JupyterLab.
5.  Install NGC by following the [instruction here](https://org.ngc.nvidia.com/setup/installers/cli) for **AMD64 Linux.** Below is an example using the `3.41.3` version.

    ```bash
    wget --content-disposition https://api.ngc.nvidia.com/v2/resources/nvidia/ngc-apps/ngc_cli/versions/3.41.3/files/ngccli_linux.zip -O ngccli_linux.zip && unzip -o ngccli_linux.zip && chmod u+x ngc-cli/ngc && echo "export PATH=\"\$PATH:$(pwd)/ngc-cli\"" >> ~/.bashrc && source ~/.bashrc
    ```
6. Run `ngc config set` with your NGC API keys.
7.  **Without creating a new folder**, create a symbolic link. (Do not repeat this step if you already have a symbolic link)

    ```bash
    # symlink bionemo to /home/sagemaker-user/bionemo. By default /home/sagemaker-user is the home directory
    # ln -s [target] [link_name]
    ln -s /workspace/bionemo /home/sagemaker-user/bionemo
    ```

    Note:

    1. The symbolic link creates a `bionemo` folder in the mandatory, default folder of `/home/sagemaker-user` that mirrors the content of `/workspace/bionemo` folder.
    2. You should always keep in mind that the folders are "mirrored" when you set up the paths etc.

### Run BioNeMo

Follow the instructions on [BioNeMo documentations](https://docs.nvidia.com/bionemo-framework/latest/index.html) to get started.

### Delete Images

1. Stop running app in SageMaker.
2. Go to SageMaker, click on **Domain**, then **Environment**. Detach and delete the image. This deletes SageMaker image and its configs.
3. Go to ECR, delete the version of the image.
