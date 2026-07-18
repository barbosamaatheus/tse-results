# Container Execution Scripts

Scripts to run experiments across multiple Docker containers with CPU control, resource monitoring, and results collection.

## Prerequisites

- Docker installed and running
- `tse-base-image` Docker image created
- JAR file: `soot-analysis-0.2.1-SNAPSHOT-jar-with-dependencies.jar`
- Python library: `psutil`

## Execution Flow

The main `run_experiment.sh` script automates this flow. If running manually, execute in this order for each dataset (`mds` or `rds`):

1. **create_containers.sh** - Creates 10 containers.
2. **clear_containers.sh [dataset]** - Clears previous state for the specified dataset.
3. **reset_results.sh [dataset]** - Removes old results and residual files for the specified dataset.
4. **update_cpus.sh** - Configures CPU pinning for each container.
5. **show_cpus.sh** - Verifies CPU configuration.
6. **install_psutil_all_containers.sh** - Installs psutil.
7. **copy_to_containers.sh** - Copies files to containers (if needed manually).
8. **run_in_all_containers.sh [dataset]** - Executes the experiment in parallel for the specified dataset.
9. **copy_results.sh [dataset] [dest]** - Copies results from containers to the host.

## Main Scripts

### create_containers.sh
Creates 10 Docker containers with 4 CPUs and 20GB RAM each.

### clear_containers.sh [dataset]
Removes residual files from previous executions inside the containers for the target dataset.

### reset_results.sh [dataset]
Cleans the `results` folder and other temporary logs for the target dataset to ensure a clean run.

### update_cpus.sh
Pins specific CPUs to each container to avoid overlapping.

### show_cpus.sh
Displays which CPUs are assigned to each container.

### install_psutil_all_containers.sh
Installs the `psutil` Python library in all containers.

### copy_to_containers.sh
Copies the JAR and Python scripts to all containers.

### run_in_all_containers.sh [dataset]
Executes the experiment in parallel across all containers for the target dataset.
- Runs: `run_organize_monit_exp.py` in each container.
- Monitors: CPU, memory, and time.

### copy_results.sh [dataset] [dest]
Copies the generated results from the containers to the host after execution finishes.
