"""
Run DiffDock in large-scale, multi-GPU, multi-target docking experiment.
Follwothe instructions in the run_diffdock_nim.ipynb to set up the input files before running this script. 
Author: Xin Yu
Date: 8/3/24
"""

import requests
import os
import pandas as pd
import numpy as np
from loguru import logger
import time, shutil
from collections import defaultdict
import pickle
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, SDWriter
import asyncio, aiofiles, aiohttp
from aiohttp import ClientTimeout


def prepare_output_directory(output, append=False):
    """
    Prepare the output directory
    output: str, the output directory
    return: None
    """
    # overwrite the output directory
    # delete the output directory if it exists
    if not append:
        if os.path.exists(output):
            shutil.rmtree(output)
        os.makedirs(output)
    else:
        os.makedirs(output, exist_ok = True)



def list_targets(base_dir):
    """
    List all target folder in the input base directory. 
    For example, base directory is: folder, the target folders are: folder/target2, folder/target2, it will return ['target1', 'target2']
    :param base_dir: str, path to the directory containing the target folders
    return: list of str, e.g. ['target1', 'target2']
    """
    targets = sorted([f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))])
    return targets


class RunDiffdockBatches:
    """
    Run DiffDock for a specific target
    """
    def __init__(self, 
                target_name,
                input_base_dir, 
                output_base_dir,   
                num_poses=40, 
                time_divisions= 20,
                steps = 18,
                max_retry = 3,
                base_url="http://localhost:8000", 
                trial_id=0, 
                repeat_one_batch = False,
                aiohttp_client_timeout = 60*60*4, # 4 hours
        ):

        """
        Initialize the class
        :param target_name: str, target name, e.g. aa2ar
        :param input_base_dir: str, input directory to the target folder: path/to/batch_input_large
        :param output_base_dir: str, output base directory, default to output/batch_output_large
        :param num_poses: int, number of poses to generate, default is 40
        :param time_divisions: int, number of time divisions, default is 20
        :param steps: int, number of diffusion steps, default is 18
        :param max_retry: int, max retry if a ligand fails, default is 3
        :param base_url: str, base url of the Diffock NIM. Default to http://localhost:8000
        :param trial_id: int, docking trial id, e.g. 0. This is optional for tracking purpose. 
        :param repeat_one_batch: bool, if True, re-run Diffdock on one of the batches. Default is False    
        :param aiohttp_client_timeout: int, timeout in seconds for aiohttp client, default is 60*60*4 seconds (4 hours). Set it at least as large as as the TRITON_TIMEOUT number.  
        """

        self.num_poses = num_poses
        self.time_divisions = time_divisions
        self.steps = steps
        self.max_retry = max_retry
        self.target_name = target_name
        self.trial_id = trial_id
        self.aiohttp_client_timeout = aiohttp_client_timeout
        self.input_base_dir = os.path.join(input_base_dir, target_name) # construct something like path/to/batch_input_large/aa2ar
        self.base_url = base_url

        # query url and health check url
        self.query_url = base_url + "/molecular-docking/diffdock/generate"
        self.health_check_url = base_url + "/v1/health/ready"

        # prepare output directory
        # output_base_dir becomes something like output/batch_output_large/5_poses_trial_0/aa2ar
        self.output_base_dir = os.path.join(output_base_dir,  f"{num_poses}_poses_trial_{trial_id}", self.target_name,)

        # if we are repeating one of many batches of this target, we should not create the output directory, because it will wipe out the other batches data.
        if not repeat_one_batch:
            prepare_output_directory(self.output_base_dir)

        # dict to keep track of server errors that require re-run
        self.server_is_ok = {}

    def create_log(self):
        """
        Optional, create a log file for all batches at the target folder. 
        return: handler_id
        """
        log_file_path = os.path.join(self.output_base_dir,  'log.log')
        handler_id = logger.add(
            log_file_path, 
            format="{time} {level} {message}", 
            level="DEBUG"
        )
        logger.info(f"Logging {self.target_name} to {log_file_path}")
        return handler_id

    def is_server_healthy(self):
        """
        Check the health of the server
        return: True if the server is healthy, False otherwise
        """
        # run health check
        response = requests.get(self.health_check_url)
        return response.text == "true"
                
    async def submit_query(self, protein_file_path, ligand_file_path):
        """
        Submit a query to the server
        :param protein_file_path: str, path to the protein PDB file
        :param ligand_file_path: str,path to the ligand txt file
        :return: dict of response, status code and JSON response content if successful, otherwise return status code and error message
        """

        async with aiofiles.open(protein_file_path, 'r') as file:
            protein_bytes = await file.read()
        async with aiofiles.open(ligand_file_path, 'r') as file:
            ligand_bytes = await file.read()

        ligand_file_type = ligand_file_path.split('.')[-1]
        
        data = {
            "ligand": ligand_bytes,
            "ligand_file_type": ligand_file_type, # should be txt here 
            "protein": protein_bytes,
            "num_poses": self.num_poses,
            "time_divisions": self.time_divisions,
            "steps": self.steps,
            "save_trajectory": False, # diffusion trajectory
            "is_staged": False
        }
        
        headers = {"Content-Type": "application/json"}

        async with aiohttp.ClientSession(timeout = ClientTimeout(self.aiohttp_client_timeout)) as session:
            async with session.post(self.query_url, headers=headers, json=data) as response:
                status_code = response.status
                try:
                    output = {
                        "status_code": status_code,
                        "response": await response.json()
                    }
                except:
                    output = {
                        "status_code": status_code,
                        "response": await response.text()
                    }
        
        return output


    async def predict_one_batch(self, batch_id, restart=True):

        """
        Run DiffDock for one batch of ligands
        :param batch_id: int, batch id
        :param restart: bool, if True, restart the prediction for this batch. This means that we set all the tasks to "pending" and "fail" to 0 in the status.csv file. Default is True
        return: None
        """

        # preapre output directory. e.g. output/batch_output_large/5_poses_trial_0/aa2ar/batch_0
        output_dir = os.path.join(self.output_base_dir, f'batch_{batch_id}')
        prepare_output_directory(output_dir)

        # add logger to the output directory. E.g. output/batch_output_large/5_poses_trial_0/aa2ar/batch_0/log.log
        logger.debug(f"{self.target_name}: Starting batch {batch_id}")
        
        # read status csv, e.g. data/batch_input_large/aa2ar/batches/batch_0/status.csv
        status_file_path = os.path.join(self.input_base_dir, 'batches', f'batch_{batch_id}', 'status.csv')
        tasks = pd.read_csv(status_file_path)

        if restart: 
            # reset status to "pending" and fail=0
            tasks['status'] = 'pending'
            tasks['fail'] = 0

        # SDF writer . Write results from one batch to one SDF file. E.g. output/batch_output_large/5_poses_trial_0/aa2ar/batch_0/output.sdf
        output_sdf_file = os.path.join(output_dir, 'output.sdf')
        writer = SDWriter(output_sdf_file)
        
        # criteria for todo tasks: status is not success or fail
        todo = tasks[(tasks['status']!='success') & (tasks['status']!='fail')]

        logger.info(f"{self.target_name} batch {batch_id}: Number of ligands to predict: {todo.shape[0]}")

        counter = 0

        while todo.shape[0] > 0:
            counter += 1
            logger.info(f"{self.target_name} batch {batch_id}: Processing batch {batch_id}, try {counter} out of max {self.max_retry} tries")

            molecule_id = list(todo.molecule_id) # 0, 1, 2. ...
            molecule_category = list(todo.category) # actives, decoys
            molecule_smiles = list(todo.smiles) # SMILES

            # write molecule smiles to a txt file so we can submit to the server, This is temporary file we will delete later. 
            tmp_ligand_txt = os.path.join(self.input_base_dir, 'batches', f'batch_{batch_id}', f'temp_ligands.txt')

            # add smiles to the txt file
            async with aiofiles.open(tmp_ligand_txt, 'w') as f:
                await f.write('\n'.join(molecule_smiles))

            logger.debug(f"{self.target_name} batch {batch_id}: Wrote ligands to temporary file: {tmp_ligand_txt}")
            logger.debug(f"{self.target_name} batch {batch_id}: Submitting query to the server...")

            result = await self.submit_query(
                protein_file_path= os.path.join(self.input_base_dir, 'receptor.pdb'),  # e.g. data/batch_input_large/aa2ar/receptor.pdb
                ligand_file_path= tmp_ligand_txt, # e.g. data/batch_input_large/aa2ar/batches/batch_0/temp_ligands.txt
            )

            status_code = result.get('status_code')
            logger.debug(f"{self.target_name} batch {batch_id}: Results received with status code: {status_code}")
            
            if status_code == 200:

                # update server status
                self.server_is_ok[batch_id] = True

                # select indices where status is success, use numpy
                status_array = np.array(result['response']['status'])
                success_indices = np.where(status_array == 'success')[0]
                failed_indices = np.where(status_array != 'success')[0]

                logger.debug(f"{self.target_name} batch {batch_id}: Number of successful ligands: {len(success_indices)}")
                logger.debug(f"{self.target_name} batch {batch_id}: Number of failed ligands: {len(failed_indices)}")
                logger.debug(f"{self.target_name} batch {batch_id}: Failed indices: {failed_indices}")
                # show status of failed ligands
                if len(failed_indices) > 0:
                    failed_status = status_array[failed_indices]
                    logger.debug(f"Status of failed ligands: {failed_status}")

                for i in success_indices:
                    # Example ligand id: actives_ligand_0, decoys_ligand_1, etc
                    ligand_id =  molecule_category[i] + '_ligand_' + str(molecule_id[i])
                    ligand_positions = result['response']['ligand_positions'][i]
                    confidence_scores = result['response']['position_confidence'][i]
                    # write to SDF file
                    for idx, sdf_str in enumerate(ligand_positions):
                        mol = Chem.MolFromMolBlock(sdf_str)
                        if mol:
                            # sanitize the molecule - disable it for slighty better speed perofrmance and save some GPU time 
                            # Chem.SanitizeMol(mol)
                            # name each molecule as active_ligand_0_pose_0, active_ligand_0_pose_1, etc
                            mol.SetProp("_Name", ligand_id+f'_pose_{str(idx)}')
                            # add confidence score as mol property
                            mol.SetProp("Confidence", str(np.round(confidence_scores[idx], 4)))
                            writer.write(mol)

                    # update status to success
                    tasks.at[i, 'status'] = 'success'
                    # reset fail to 0
                    tasks.at[i, 'fail'] = 0
                
                # update status to failed for failed indices. Check if we should retry. 
                for i in failed_indices:
                    tasks.at[i, 'fail'] += 1
                    tasks.at[i, 'status'] = 'failed' if tasks.at[i, 'fail'] >= self.max_retry else 'retry'

                logger.info(f"{self.target_name} batch {batch_id}: Number of successful ligands: {len(success_indices)} out of {todo.shape[0]}")
                logger.info(f"{self.target_name} batch {batch_id}: Number of failed ligands: {len(failed_indices)} out of {todo.shape[0]}")
            
            # handle triton server error. 
            else:
                # update server status
                self.server_is_ok[batch_id] = False
                logger.error(f"{self.target_name} batch {batch_id}: Error, status code: {status_code}")
                logger.error(f"{self.target_name} batch {batch_id}: Error message: {result['response']}")
                logger.error(f"{self.target_name} batch {batch_id}: Stop the prediction for this batch. You need to manually inspect")
                # force fail the entire run to allow manual inspection
                tasks['status'] = 'fail'
                tasks['fail'] = 1
                break
            todo = tasks[(tasks['status']!='success') & (tasks['status']!='fail')]

        # close the SDF writer
        writer.close()

        # save the status to the csv file ,e.g. output/batch_output_large/5_poses_trial_0/aa2ar/batch_0/status.csv
        output_status_file = os.path.join(output_dir, 'status.csv')
        tasks.to_csv(output_status_file, index=False)

        # remove the temp_ligands.txt file
        os.remove(tmp_ligand_txt)

        logger.success(f"{self.target_name} batch {batch_id}: Completed")
        logger.info(f"{self.target_name} batch {batch_id}: Saved SDF file: {output_sdf_file}")
        logger.info(f"{self.target_name} batch {batch_id}: Saved status file: {output_status_file}")

    async def _run_all_batches(self, batch_id):
        await self.predict_one_batch(batch_id, restart=True)

    async def run_all_batches(self):
        """
        Run all batches of the target
        return: None
        """
        
        # read batch_0, batch_1, etc. from the data/batch_input_large/aa2ar/batches folder
        batches = os.listdir(os.path.join(self.input_base_dir, 'batches'))
        logger.debug(f"{self.target_name}: Batches: {batches}")
        logger.info(f"{self.target_name}: Number of batches: {len(batches)}")

        # make sure there are more than 1 batch
        if len(batches) == 0:
            logger.error(f"{self.target_name}: No batches found in {self.input_base_dir}")
            raise ValueError(f"{self.target_name}: No batches found in {self.input_base_dir}")

        tasks = [self._run_all_batches(batch_id) for batch_id in range(len(batches))]
        await asyncio.gather(*tasks)
        

if __name__ == "__main__":
    
    # update these variables
    input_base_dir = 'data/batch_input_large'
    output_base_dir = 'output/batch_output_large'
    num_poses = 5 # number of poses to generate
    time_divisions= 20 # number of time divisions
    steps = 18 # number of diffusion steps
    max_retry = 2 # max number of retries
    base_url = "http://localhost:8000" # server url
    trial_id = 0 # trial id (for bookkeeping)
    aiohttp_client_timeout = 60*60*4 # 4 hours

    # select a subset of targets to run, if needed
    # all targets
    targets = list_targets(input_base_dir)
    start_idx_inclusive = 0 
    end_indx_inclusive = len(targets)-1

    # -------- iterate through each target ------------
    targets_subset = targets[start_idx_inclusive:end_indx_inclusive+1]
    print(f"Running for targets: {targets_subset}")

    handler_id = None

    for target_name in targets_subset:

        # remove existing loguru handlers
        if handler_id is not None:
            logger.remove(handler_id)

        myrun = RunDiffdockBatches(
            trial_id=trial_id, 
            num_poses=num_poses, 
            time_divisions=time_divisions,
            steps=steps,
            max_retry = max_retry,
            target_name = target_name,
            input_base_dir = input_base_dir, 
            output_base_dir = output_base_dir, 
            base_url=base_url,
            aiohttp_client_timeout=aiohttp_client_timeout
        )

        # create log file for all batches at the target folder
        handler_id = myrun.create_log()

        # check server health
        assert myrun.is_server_healthy(), "Server is not healthy"
        logger.info("Server is healthy")

        start = time.time()
        asyncio.run(myrun.run_all_batches())
        end = time.time()
        logger.info(f"Total seconds taken: {end - start}")

        # check if server is ok for all batches, if not print failed batches: 
        failed_batches = [batch_id for batch_id, is_ok in myrun.server_is_ok.items() if not is_ok]
        if len(failed_batches) > 0:
            logger.error(f"Server failed for {target_name} batches: {failed_batches}")
            logger.error("Manual inspection required for these batches. ")
        else:
            logger.success(f"Server successfully responded to all batches of {target_name}")

        # save time info into a pickle file
        with open(os.path.join(myrun.output_base_dir, 'time.pkl'), 'wb') as f:
            pickle.dump({
                'total_runtime_sec': np.round(end-start ,3), 
                'failed_batches': failed_batches
        }, f)

        logger.success(f"All batches of {target_name} completed")

    print("All targets completed!")
