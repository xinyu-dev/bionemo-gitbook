# Quick Start

## Prerequisites

1. Complete the **NIM Setup** section.

## Steps for running on SageMaker notebook

{% hint style="info" %}
Follow [virtual screening blueprint official docs here](https://github.com/NVIDIA-NIM-Agent-Blueprints/generative-virtual-screening/tree/main)
{% endhint %}

### Create a lifecycle config

Create a **Notebook Instance** (NOT JupyterLab) life cycle configuration script to setup docker compose and NGC.

```bash
#!/bin/bash

set -e

# Set up ngc-cli
cd /home/ec2-user/SageMaker

# ngc
# Install ngc-cli package
wget --content-disposition https://api.ngc.nvidia.com/v2/resources/nvidia/ngc-apps/ngc_cli/versions/3.48.0/files/ngccli_linux.zip -O ngccli_linux.zip && unzip -o ngccli_linux.zip
chmod u+x ngc-cli/ngc
echo "export PATH=\"\$PATH:$(pwd)/ngc-cli\"" >> ~/.bashrc && source ~/.bashrc

# Change ownership to ec2-user, otherwise pip install fails
sudo chown -R ec2-user:ec2-user /home/ec2-user/SageMaker

# switch to ec2-user
sudo -u ec2-user -i <<'EOF'

# Use base environment. Set default environment to python3 
ENVIRONMENT="python3"

source /home/ec2-user/anaconda3/bin/activate "$ENVIRONMENT"

# ngc cli path for conda env
echo "export PATH=\"\$PATH:/home/ec2-user/SageMaker/ngc-cli\"" >> $(conda info --base)/envs/$ENVIRONMENT/etc/conda/activate.d/env_vars.sh

# install docker compose. SageMaker notebook has docker installed, but not docker compose.
DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
mkdir -p $DOCKER_CONFIG/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.29.2/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose
chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose

EOF

# restart command is dependent on current running Amazon Linux and JupyterLab
CURR_VERSION=$(cat /etc/os-release)
if [[ $CURR_VERSION == *$"http://aws.amazon.com/amazon-linux-ami/"* ]]; then
	sudo initctl restart jupyter-server --no-wait
else
	sudo systemctl --no-block restart jupyter-server.service
fi
```

### Launch notebook

1. In SageMaker console, click on the **Notebooks** on the left side bar (NOT the Studio).
2. Launch a SageMaker notebook with the following configs:
   1. Instance: `g5.16xlarge`
   2. Volume: `800 GB` (AlphaFold data requires 500 G)
   3. Lifecycle config: select your life cycle config
   4. Root access: `Enabled`
   5. VPC: Use SageMaker default

### Credentials

1.  Once inside the JupyterLab, run the following. Note that MY\_KEY is the same in both cases.

    ```bash
    echo "export NGC_API_KEY=MY_KEY" >> ~/.bashrc \
    && source ~/.bashrc
    ```

    Then run :

    ```bash
    echo "export NGC_CLI_API_KEY=MY_KEY" >> ~/.bashrc \
    && source ~/.bashrc
    ```
2.  After the command, activate the `python3` conda environment again, with

    ```bash
    source /home/ec2-user/anaconda3/bin/activate python3
    ```
3.  Log into docker with `$oauthtoken` as username and your API key above as password.&#x20;

    ```bash
    docker login nvcr.io
    ```

### Redirect docker to container images elsewhere

{% hint style="danger" %}
If you do not do this step, you might get an error saying the default `/tmp` is out of capacity
{% endhint %}

1.  Check which volume has enough space.

    ```
    df -h
    ```
2.  Create a folder called `docker` at the volume where you want to store the docker containers. In this example, we will create a folder with `sudo` like this:

    ```bash
    sudo mkdir -p /home/ec2-user/SageMaker/docker
    ```

    **the `sudo` command is very important.** Without it you might get errors.
3.  Run

    ```bash
    sudo nano /etc/docker/daemon.json
    ```
4.  Then add the `data-root` line to change the download folder of docker containers:

    ```json
    {
        "runtimes": {
            "nvidia": {
                "args": [],
                "path": "nvidia-container-runtime"
            }
        },
        "data-root": "/home/ec2-user/SageMaker/docker"
    } 
    ```
5.  Then restart docker container with

    ```bash
    sudo systemctl restart docker
    ```

### First time running

Open jupyter lab terminal, create a folder for model weights

```bash
mkdir /home/ec2-user/SageMaker/nim
```

### Cache model weights

1.  Run

    ```bash
    chmod -R 777 /home/ec2-user/SageMaker/nim
    ```
2.  Export the env variables:

    ```bash
    echo "export ALPHAFOLD2_CACHE=/home/ec2-user/SageMaker/nim" >> ~/.bashrc && source ~/.bashrc \
    && echo "export DIFFDOCK_CACHE=/home/ec2-user/SageMaker/nim" >> ~/.bashrc && source ~/.bashrc \
    && echo "export MOLMIM_CACHE=/home/ec2-user/SageMaker/nim" >> ~/.bashrc && source ~/.bashrc
    ```

### Additional packages

Optionally, install these additional packages so that you can work with example notebook. These are not required for the blueprint though.

```bash
conda activate python3 && conda install conda-forge::pymol-open-source
```

```
pip install py3dmol biopython rdkit
```

### Verify docker compose

Verify docker compose is correctly installed:

```
docker compose version
```

If not, run

```bash
# install docker compose. SageMaker notebook has docker installed, but not docker compose.
DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker} \
&& mkdir -p $DOCKER_CONFIG/cli-plugins \
&& curl -SL https://github.com/docker/compose/releases/download/v2.29.2/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose \
&& chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
```

### Launch containers

1.  Run

    ```bash
    git clone https://github.com/NVIDIA-NIM-Agent-Blueprints/generative-virtual-screening.git
    ```

    Or use my forked repo with modifications:

    ```bash
    git clone https://github.com/xinyu-dev/generative-virtual-screening.git
    ```
2.  Run

    ```bash
    cd generative-virtual-screening/deploy
    ```
3.  Run

    ```bash
    docker compose up
    ```
4. There are log you will see sections:
   1. `deploy-diffdock-1`
   2. `deploy-molmim-1`
   3. `deploy-alphafold-1`
   4. You should see `Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)` for each of the 3 parts in the log

### Health check

Open a terminal inside the notebook, run the following healthcheck, line by line, for each model:

```
# alphafold
curl localhost:8081/v1/health/ready

# Diffdock
curl localhost:8082/v1/health/ready

# molmim
curl localhost:8083/v1/health/ready
```

{% hint style="danger" %}
There is a bug with current workflow that AlphaFold weights are not correctly downloaded. healthcheck for Diffdock and MolMIM will return `True`, but health check for AlphaFold return errors. In this case, go to Troubleshooting section on this page for workarounds.&#x20;
{% endhint %}

### Run notebook

1. Head over to the `generative-virtual-screening/src/generative-virtual-screening.ipynb`

## Troubleshooting

### Check if data is downloaded completely

```bash
du -sh alphafold2-data_v1.0.0/
```

Should result in 509G .

```bash
du -sh bionemo-diffdock_v1.2.0/
```

Should result in 2.6G

```bash
du -sh molmim_v1.3/
```

Should result in 269M



### AlphaFold health check fails

Check if data has been downloaded completely:

```bash
du -sh alphafold2-data_v1.0.0/
```

Size should be 509G. If you did not download the entire dataset, try download and cache the dataset by running just the AlphaFold NIM. Steps:

1. If you still have `docker compose up` running, kill the process.
2.  Remove the exiting data folder

    ```bash
    rm -r alphafold2-data_v1.0.0/
    ```
3.  Run

    ```bash
    export LOCAL_NIM_CACHE=/home/ec2-user/SageMaker/nim
    ```
4.  Confirm credentials

    ```bash
    echo $NGC_CLI_API_KEY
    ```
5.  Run

    ```bash
    docker run --rm --name alphafold2 --runtime=nvidia \
        -e NGC_CLI_API_KEY \
        -v $LOCAL_NIM_CACHE:/opt/nim/.cache \
        -p 8000:8000 \
        nvcr.io/nim/deepmind/alphafold2:1.0.0
    ```
6.  The download will take \~3 hours. During which, you can check the status

    ```bash
    du -sh /home/ec2-user/SageMaker/nim/alphafold2-data_v1.0.0/
    ```
7. Once done, AlphaFold NIM server will launch. Stop that server. Then run `docker compose up` again

### Diffdock fails to launch

When you run `docker compose up`, you might get an error saying AlphaFold NIM is ready, but Diffdock keeps waiting for triton server, and eventually times out. To fix it, remove the previously cached weights:

```bash
rm -r $LOCAL_NIM_CACHE/bionemo-diffdock-v1.2.0
```

Then rerun `docker compose up`
