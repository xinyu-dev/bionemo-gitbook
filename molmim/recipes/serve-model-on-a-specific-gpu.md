# Serve model on a specific GPU

The `inference.ipynb` and `inference_interactive.ipynb` uses triton to serve the model. By default the model is served on GPU:0. You can specify an environment variable to assign the model to a different GPU:

```python
CUDA_VISIBLE_DEVICES=0 # use GPU:0, OR
CUDA_VISIBLE_DEVICES=1 # use GPU:1
# etc
```

See detailed example below

## Example: Use GPU:1 on localhost to serve MolMIM for inference

### Prerequisite

1. Set up BioNeMo and have Jupyter Lab instance running.

### Steps

{% hint style="info" %}
The following example sets up a local triton server and uses `inference.ipynb`
{% endhint %}

1.  Find `infer.yaml` file for the model. For example, for MolMIM, it is located at `/workspace/bionemo/examples/molecule/molmim/conf/infer.yaml` Make sure the model path is is correct (if you follow the setup guide on this site, it should be good).
    ```yaml
    downstream_task:
        restore_from_path: ${oc.env:BIONEMO_HOME}/models/molecule/molmim/molmim_70m_24_3.nemo
    ```
2.  Open a terminal, then export environment variable. For example, to use GPU:1 instead of GPU:0, type:
    ```bash
    export CUDA_VISIBLE_DEVICES=1
    ```
3.  In the **same** terminal, run
    ```bash
    python -m bionemo.triton.inference_wrapper \
    --config-path /workspace/bionemo/examples/molecule/molmim/conf \
    --config-name infer.yaml
    ```
    * `--config-path`: this should point to the folder that contains the YAML file
    * `--config-name`: this should point to `infer.yaml`
4. Wait for ~ 2 minutes for the triton to finish launching. 
5. Go to `/workspace/bionemo/examples/molecule/molmim/nbs/Inference.ipynb`. Run through the blocks. The model is now served on GPU:1. You can verify this by opening a new terminal, and run nvidia-smi. It should show something like this: 
    ![molmim-change-gpu](/.gitbook/assets/images/molmim-change-gpu.jpg)
6. To kill the triton server and release memory, go to the terminal where you have the triton server running, and press `contrl+c` to stop the server.
