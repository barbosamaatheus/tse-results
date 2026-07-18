# MissReference Analysis Scripts

This directory contains scripts used to identify missing reference resolutions in the static analysis tools, by comparing the call graph outputs (CHA, RTA, VTA) against the baseline (`PANotResolve.csv` from SPARK).

## Structure

- **MergeDataset/**: Contains the orchestrator script `run_all_missref.py` tailored for the MDS dataset outputs (handling ICF, IDFP, and IOA structures).
- **RefDataset/**: Contains the orchestrator script `run_all_missref.py` tailored for the RDS dataset outputs (handling the internal results structures).

## Execution Flow

The `run_all_missref.py` script acts as an orchestrator that runs multiple sub-scripts sequentially to:
1. Extract outputs with missing references (`1outputWithMissReference.py`).
2. Verify missing references on conflicts (`2hasMissReferenceOnConflict.py`).
3. Link the conflict paths and summarize the counts (`3linkConflictPathHasMissReferenceWithResults.py`).

## How it works within the pipeline

The `run_experiment.sh` automatically performs the necessary data staging for these scripts. It copies the `resultsX` folders or the processed output folders from the main experiment run into this directory (`missRef/`) because `run_all_missref.py` treats `missRef/` as the `PROJECT_ROOT`. After the scripts compute the missing references and generate `CF`, `DF`, `OA` folders, `run_experiment.sh` moves these results to the final output structure.
