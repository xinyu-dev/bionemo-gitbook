# Zero-Shot Mutant Design

## Prerequisites

1. Set up the BioNeMo Framework container 
2. You will also need pretrained model checkpoint `.nemo` file. You can either use the pretrained models we provided or train your own.  


## Background
Given a sequence, we embed it with ESM2nv. The logits returned by the model represent the probability prediction for each token at each position. The probabilty matrix can then be used for zero-shot protein and antibody designs as described by [Hie et al](https://www.nature.com/articles/s41587-023-01763-2), which utilizes ESM models to design point mutations to improve the potency and breadth of SARS-Cov-2 antibodies. 

Below is a screenshot using lysozyme as an example. The original sequence is shown above, the ESM2nv predicted sequence is shown below. Alignment suggests 2 positions for mutatant design. 
<figure><img src="../.gitbook/assets/images/notebook_lysozyme_zero_shot.png" alt="Zero-shot protein design"><figcaption><p></p></figcaption></figure>

## Steps
Refer to [this notebook](../.gitbook/assets/notebooks/esm2nv/zero_shot_protein_design.ipynb)
