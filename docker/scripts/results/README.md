# Results Processing Scripts

This directory contains scripts responsible for parsing, organizing, and summarizing the outputs of the executed static analysis tools.

## Scripts

1. **mds_results.py**
   - Processes the raw outputs specifically for the **MergeDataset (MDS)**.
   - Extracts relevant metrics, identifies false positives/negatives, and formats the results into aggregated formats like `icf`, `ioa`, and `idfp` directories.

2. **rds-results.py**
   - Processes the raw outputs specifically for the **RefDataset (RDS)**.
   - Extracts evaluation metrics and parses the output for reference resolution.

## How it works within the pipeline

The orchestrator script `run_experiment.sh` automatically copies the raw `results1/` outputs generated from the container execution into this directory, depending on whether it is processing MDS or RDS. It then calls the respective script, which processes these files and outputs CSVs, text summaries, and structured subdirectories, which are then moved to the final structured output folder (`experiment_out_<timestamp>`).
