# Docker Experiment Runner

This directory contains the necessary scripts and Dockerfile to execute the experimental evaluation for the replication package. The experiments run across multiple Docker containers to execute static analysis tools in parallel.

## Structure

- `Dockerfile`: Defines the base image `tse-base-image`, which includes Java, Maven, Python, and the required project repositories and datasets.
- `run_experiment.sh`: The main orchestrator script. It automates the entire process of building the image, creating the containers, running the pipelines for both the **MergeDataset (MDS)** and **RefDataset (RDS)** sequentially, and eventually analyzing and collecting the results.
- `scripts/`: Contains the individual shell and Python scripts for container lifecycle management, execution, and statistical analysis.

## Usage

To execute the entire replication pipeline (running both MDS and RDS sequentially):

```bash
bash run_experiment.sh [NUM_CONTAINERS] [TARGET_DATASET]
```

- `[NUM_CONTAINERS]` is optional (defaults to 10).
- `[TARGET_DATASET]` is optional (defaults to `all`). It can be `all`, `mds`, or `rds`.

### Running Specific Datasets

If you wish to test or run only the **MergeDataset (MDS)** pipeline, pass `mds` as the second argument:
```bash
bash run_experiment.sh 10 mds
```

If you wish to run only the **RefDataset (RDS)** pipeline, pass `rds`:
```bash
bash run_experiment.sh 10 rds
```

### Saving Execution Logs (Windows)

If you are running the scripts in a Windows environment (like CMD or PowerShell), it is highly recommended to redirect the output to a log file to capture any errors.

**Using Command Prompt (CMD):**
```cmd
cd docker
bash run_experiment.sh 10 > experiment_run.log 2>&1
```

**Using PowerShell:**
```powershell
cd docker
bash run_experiment.sh 10 2>&1 | Tee-Object -FilePath "experiment_run.log"
```

The script will:
1. Build the Docker image.
2. Create the containers.
3. Execute the analysis pipeline for MDS and collect its results.
4. Clean up, then execute the analysis pipeline for RDS and collect its results.
5. Process the collected results using the statistical analysis and miss-reference scripts.
6. Output a structured directory (`experiment_out_<timestamp>`) containing the final metrics, CSVs, and PDFs.

For more details on the sub-scripts, check the individual READMEs in the `scripts/` directory.