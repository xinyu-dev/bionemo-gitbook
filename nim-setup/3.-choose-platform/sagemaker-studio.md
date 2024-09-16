# SageMaker Studio

## Prerequisites

{% content-ref url="../1.-request-nim-access.md" %}
[1.-request-nim-access.md](../1.-request-nim-access.md)
{% endcontent-ref %}

{% content-ref url="../2.-configure-ngc-api-key.md" %}
[2.-configure-ngc-api-key.md](../2.-configure-ngc-api-key.md)
{% endcontent-ref %}

## Steps for launching NIM on SageMaker Studio JupyterLab

{% hint style="info" %}
This method allows you to run BioNeMo NIMs on SageMaker JupyterLab as a local host or a remote host. It utilizes a similar method as described in [AWS blog on jupyterlab proxy](https://aws.amazon.com/blogs/machine-learning/accelerate-ml-workflows-with-amazon-sagemaker-studio-local-mode-and-docker-support/). The advantage of this method is that 1) relatively simple 2) does not require converting BioNeMo functions to SageMaker functions. 3) can run on single-GPU or multi-GPU as long as it is a single node. The disadvantage is that it does not support multi-node inference. For multi-node inference, refer to the [NIM+shim guide](https://github.com/NVIDIA/nim-deploy/blob/main/cloud-service-providers/aws/sagemaker/README\_shell.md)
{% endhint %}

### Domain

1. Create a SageMaker domain with AWS's  **quick set up** option.
2.  Enable docker by running the following command in the terminal:

    ```shell
    aws --region us-east-1 sagemaker update-domain --domain-id <your_id> --domain-settings-for-update '{"DockerSettings": {"EnableDockerAccess": "ENABLED"}}'
    ```

    `region` is required. Change it to the region where your domain is located. `domain-id` is required: change the ID to your domain ID.&#x20;

### Life cycle config

In SageMaker console, click on the **life cycle config** option on the left bar. Then create a **JupyterLab** life cycle configuration script to setup docker and NGC. Below is an example:&#x20;

```bash
#!/bin/bash

set -e

# ngc
# Install ngc-cli package
# note the -o flag, which overwrites files without asking for confirmation. 
# this is important because the script will be run each time a new container is created
# but our ngc is cached inside the EBS which persists data across different runs of the same Jupyterlab App
wget --content-disposition https://api.ngc.nvidia.com/v2/resources/nvidia/ngc-apps/ngc_cli/versions/3.41.3/files/ngccli_linux.zip -O ngccli_linux.zip && unzip -o ngccli_linux.zip
chmod u+x ngc-cli/ngc
echo "export PATH=\"\$PATH:$(pwd)/ngc-cli\"" >> ~/.bashrc && source ~/.bashrc

# install docker
sudo apt-get update

sudo apt-get install ca-certificates curl gnupg -y

sudo install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

sudo chmod a+r /etc/apt/keyrings/docker.gpg


sudo echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "${VERSION_CODENAME:-jammy}")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get -y update


# pick the latest patch from:
# apt-cache madison docker-ce | awk '{ print $3 }' | grep -i 20.10
# this will result something like 5:20.10.24~3-0~ubuntu-jammy
# note that studio only supports 20.10 as of Aug 2024

VERSION_STRING=$(apt-cache madison docker-ce | awk '{ print $3 }' | grep -i 20.10 | head -n 1)

sudo apt-get install docker-ce-cli=$VERSION_STRING docker-compose-plugin -y

# validate the Docker Client is able to access Docker Server at [unix:///docker/proxy.sock]
if [ -z "${DOCKER_HOST}" ]; then
  export DOCKER_HOST="unix:///docker/proxy.sock"
fi

```

Once you save the life cycle config to SageMaker, go to the **Domains -> Environment** tab, and **attach** the life cycle config to your Studio Domain:&#x20;

<figure><img src="../../.gitbook/assets/image (3).png" alt=""><figcaption></figcaption></figure>

### Create JupyterLab App

In the SageMaker Studio, create a JupyterLab space with:

1. `g5.16xlarge` instance
2. 100 G EBS volume (or at least 600G if running AlphaFold NIM)
3.  Select your life cycle config script.&#x20;

    <figure><img src="https://res.cloudinary.com/dpfqlyh21/image/upload/v1726511930/obsidian/bjio2b93s95q84kzhniv.png" alt=""><figcaption></figcaption></figure>
4. LClick **Run Space** to launch the JupyterLab app

### Configure NGC and Docker

1. Open up a terminal in JuptyerLab app.
2.  Configure NGC with:

    ```shell
    ngc config set
    ```
3.  Log into docker with:

    ```shell
    docker login nvcr.io
    ```

    Username should be exactly the phrase `$oauthtoken` . Password should be NGC API key.
4.  Check if `NGC_API_KEY` environment variable already exists

    ```shell
    echo $NGC_API_KEY
    ```

    If returns nothing, set it by

    ```shell
    echo "export NGC_API_KEY=YOUR_API_KEY" >> ~/.bashrc \
    && source ~/.bashrc
    ```

### Download container

{% hint style="danger" %}
SageMaker Studio has limited support for docker. See [here](https://aws.amazon.com/blogs/machine-learning/accelerate-ml-workflows-with-amazon-sagemaker-studio-local-mode-and-docker-support/) for more details
{% endhint %}

We will use Diffdock as an example:

```bash
docker pull nvcr.io/nim/mit/diffdock:1.2.0
```

### Launch NIM

1.  cache the model weights and triton configs in local volume, so that you don't have to re-download the model every time you launch the NIM container. Assuming that we will create this cache folder at `~/nim` , run:

    ```bash
    export LOCAL_NIM_CACHE=~/nim && mkdir -p "$LOCAL_NIM_CACHE" && chmod 777 $LOCAL_NIM_CACHE
    ```
2.  I also recommend adding this to bash profile, so that next time you do not have to set it again

    ```bash
    echo "export LOCAL_NIM_CACHE=~/nim" >> ~/.bashrc \
    && source ~/.bashrc
    ```
3.  Then run

    ```bash
    docker run --rm -it --name diffdock-nim \
      --gpus all \
      -e NGC_API_KEY=$NGC_API_KEY \
      -v "$LOCAL_NIM_CACHE:/home/nvs/.cache/nim" \
      --net sagemaker \
      nvcr.io/nim/mit/diffdock:1.2.0
    ```

    * `-p` : not allowed
    * `-v`: allowed, but the volume to be mounted must be in EBS volume
    * `--net sagemaker`: must add
4.  Wait until it says something like this

    ```
    Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
    ```

### Health check locally

Open a new terminal in JupyterLab and run

```bash
curl localhost:8000/v1/health/ready
```

Should return `True`

### Create a remote session

{% hint style="danger" %}
* Use only JupyterLab app. Code Editor did not work with remote server as of 8/20/24.
* You must create a `boto3` session to authenticate. Simply use `curl` on command line did not work
{% endhint %}

1.  Test the application by opening a new window on **browser**. Then type the following url:

    ```
    https://<space-id>.studio.us-east-1.sagemaker.aws/jupyterlab/default/proxy/8000/v1/health/ready
    ```

    Replace `<space-id>` with the actual id of your space. The browser should show `true`
2.  Open a notebook in your local laptop. Create a boto3 session. Note that `aws_session_token` might not be necessary, depending on how your AWS account is set up.&#x20;

    ```python
    import boto3, requests
    session = boto3.Session(
    	    aws_access_key_id='my_key',
    	    aws_secret_access_key='my_secrete_key',
    	    aws_session_token='my_token'
    )
    ```
3.  Test the connection by listing buckets

    ```python
    # Test connection by listing buckets
    s3_client = session.client('s3')
    s3_client.list_buckets()
    ```
4.  Copy this function to use for creating presigned domain url

    ```python
    def create_presigned_domain_url(domain_id, user_profile_name, space_name, seession_expiration_duration_in_seconds=43200, expires_in_seconds=300):

        """
        Create a presigned domain URL for a SageMaker domain
        :param domain_id: str, the ID of the SageMaker domain
        :param user_profile_name: str, the name of the user profile
        :param space_name: str, the name of the space (JupyterLab App)
        :param seession_expiration_duration_in_seconds: int, the duration of the session expiration, default is 43200 seconds (12 hours)
        :param expires_in_seconds: int, the duration of the presigned URL expiration, default is 300 seconds (5 minutes)
        :return: str, the presigned domain URL, or None if an error occurs
        """
        # Initialize a SageMaker client
        sagemaker_client = boto3.client('sagemaker')

        try: 
        # Create the presigned domain URL
            response = sagemaker_client.create_presigned_domain_url(
                DomainId=domain_id,
                UserProfileName=user_profile_name,
                SpaceName=space_name, 
                SessionExpirationDurationInSeconds=seession_expiration_duration_in_seconds, 
                ExpiresInSeconds=expires_in_seconds
            )
            presigned_url = response.get('AuthorizedUrl', None)
            return presigned_url  
        except Exception as e:
            print(f"Error creating presigned domain URL: {e}")
            return None
    ```
5.  Then get a presigned url

    ```python
    # Example usage
    domain_id = 'my-domain-id'
    user_profile_name = 'xiyu'
    space_name = 'bionemo-nim' # name of the Jupyterlab app

    presigned_url = create_presigned_domain_url(domain_id, user_profile_name, space_name)   
    print(f"{presigned_url}")
    ```

    It will show something like this:

    ```
    https://yexx4faui3i0k2x.studio.us-east-1.sagemaker.aws/auth?token=<SOMETOKEN>
    ```

    If you paste the above URL in browser, you can actually log into SageMaker Studio from anywhere allowed by your security group. You do not need separately sign into AWS first.
6.  Create a session with presigned url

    ```python
    # create a session with the presigned URL
    session = requests.Session()
    response = session.get(presigned_url)
    assert response.status_code == 200
    ```

### Build urls

First, go to the running JuptyerLab. Find the `sagemaker-space-id` on your **browser**. It looks something like this:

```
https://<sagemaker-space-id>.studio.us-east-2.sagemaker.aws/jupyterlab/default/
```

Then:

```python
sagemaker_space_id = 'yexx4faui3i0k2x' # replace with your space id
base_url = f'https://{sagemaker_space_id}.studio.us-east-1.sagemaker.aws/jupyterlab/default/proxy/8000'
health_check_url = f'{base_url}/v1/health/ready'
query_url = f'{base_url}/molecular-docking/diffdock/generate'
```

### Run health check remotely

```python
response = session.get(health_check_url)
assert response.text == "true", "Health check failed"
```

### Submit query remotely

```python
def submit_query(protein_file_path, ligand_file_path, num_poses=20, time_divisions=20, steps=18):
    """
    Submit a query to the server
    :param protein_file_path: path to the protein file, must be a PDB file
    :param ligand_file_path: path to the ligand file, must be a txt, SDF, MOL2, file. If using batch-docking, only txt and SDF are supported. 
    :param num_poses: int, number of poses to be generated, default is 20
    :param time_divisions: int, number of time divisions, default is 20
    :param steps: int, number of diffusion steps, default is 18
    :return: dict of response, status code and JSON response content if successful, otherwise return status code and error message
    """

    with open(protein_file_path, 'r') as file:
        protein_bytes = file.read()
    with open(ligand_file_path, 'r') as file:
        ligand_bytes = file.read()

    ligand_file_type = ligand_file_path.split('.')[-1]
    
    data = {
        "ligand": ligand_bytes,
        "ligand_file_type": ligand_file_type, # txt, sdf, mol2
        "protein": protein_bytes,
        "num_poses": num_poses,
        "time_divisions": time_divisions,
        "steps": steps,
        "save_trajectory": False, # diffusion trajectory
        "is_staged": False
    }
    
    headers = {"Content-Type": "application/json"}

    response = session.post(query_url, headers=headers, json=data)
    status_code = response.status_code
    try:
        response.raise_for_status() # optional, immediately fails if the status code is not 200
        output = {
            "status_code": status_code,
            "response": response.json()
        }
    except:
        output = {
            "status_code": status_code,
            "response": response.text()   
        }
    
    return output

```

Then run

```python
%%time
result = submit_query(
    protein_file_path="data/batch_input_small/receptor.pdb",
    ligand_file_path="data/batch_input_small/input_smiles.txt",
    num_poses=5, 
    time_divisions=20, 
    steps=18
)
```

