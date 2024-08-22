# This script creates a subset of SWE-bench-verfied which:
# 1) Contains all of the repositories in SWE-bench verified
# 2) For each repository, contains an example where swe_agent + Claude 3.5 + Sonnet resolved the issue, and an example where it did not (Some repositories may not have examples where the issue was resolved, in this case we only include a single example where the issue was not resolved)
# The outputs of this script are cached as part of the respository, this script allows us to edit this the dataset.
import json
from datasets import load_dataset
from pathlib import Path
import os
import pandas as pd

dataset = load_dataset("princeton-nlp/SWE-bench_Verified")["test"]

results_per_repo = {}
logs_dir = Path(__file__).parent / "20240620_sweagent_claude3.5sonnet" / "logs" # To run this script, you must download local copy from https://github.com/swe-bench/experiments/tree/main/evaluation/verified/20240620_sweagent_claude3.5sonnet/
results = []
missing_results = []

# Load results from the log directory
for result in os.listdir(logs_dir):
    results_path = os.path.join(logs_dir, result,"report.json")
    if  os.path.exists(results_path):
        with open(results_path, "r") as f:
            result_dict = json.load(f)
            result_name, results_value = next(iter(result_dict.items()))
            output_dict = dict(instance_id=result_name,**results_value)
            patch_path = os.path.join(logs_dir, result,"patch.diff")
            with open(patch_path, "r") as f:
                output_dict["swe_agent_patch"] = f.read()
            results.append(output_dict)

    else:
        missing_results.append(result)

# Get repository name from the results
results = pd.DataFrame.from_records(results)
results["repo"] = results["instance_id"].apply(lambda x: x.split("__")[0])

# Group by repository, and success. Then pick one from each group.
results_per_repo = results.groupby(["repo", "resolved"])
results_per_repo = results_per_repo.apply(lambda x: x.sample(1)).reset_index(drop=True)

# We skip matplotlib as it takes too long to build the images (~2 hours)
results_per_repo = results_per_repo[results_per_repo["repo"] != "matplotlib"]

# Filter dataset by those instance ids, and add a "reolved_by_swe_agent" column.
instance_ids = results_per_repo["instance_id"].values
resolved = results_per_repo["resolved"].values

dataset = dataset.filter(lambda x: x["instance_id"] in instance_ids)
dataset = dataset.map(lambda x: dict(x, resolved_by_swe_agent=resolved[instance_ids == x["instance_id"]][0]))

# Calculate the accuracy. Should be 0.42105263157894735.
accuracy = sum(resolved) / len(resolved)


# Save tbe dataset
dataset_dir = Path(__file__).parent / "all_repos_swe_agent_50_percent.hf"
os.makedirs(str(dataset_dir), exist_ok=True)
dataset.to_parquet(dataset_dir / "dataset.parquet")

print(f"Saved dataset to {dataset_dir}, accuracy {accuracy}")