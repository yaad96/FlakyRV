import os
import subprocess
import optuna
import re
import shutil
import sys
import glob

result_filename = None

def optimize_repo(project, sha, n_trials=100, seed=None):
    def objective(trial):
        try:
            k = round(trial.suggest_float('alpha', 0.01, 0.99, step=0.01), 2)
            j = round(trial.suggest_float('epsilon', 0.01, 0.99, step=0.01), 2)

            install_command = f"bash install.sh true false {k} {j} > /dev/null 2>&1"
            subprocess.run(install_command, shell=True)

            output_dir = f"output-{project.split('/')[1]}"
            collect_command = f"bash collect_traces.sh {project} {sha} {output_dir} >> exec_result.txt"
            subprocess.run(collect_command, shell=True)

            with open("exec_result.txt", "r") as file:
                content = file.read()
                time_match = re.search(r'(\d+) ms', content)
                if time_match:
                    time_value = int(time_match.group(1)) 
                else:
                    time_value = float('inf')

            trial.set_user_attr("time", time_value)

            unique_traces = 0
            trace_files = glob.glob(f"{output_dir}/all-traces*/unique-traces.txt")
            for trace_file in trace_files:
                with open(trace_file, "r") as file:
                    unique_traces += len(file.readlines()) - 1

            shutil.rmtree(output_dir)
            if os.path.exists("exec_result.txt"):
                os.remove("exec_result.txt")

            return unique_traces

        except Exception as e:
            raise optuna.TrialPruned(f"Trial pruned due to error: {e}")

    repo_name = project.split('/')[1]
    db_file = f"study-{repo_name}.db"
    storage_url = f"sqlite:///study-{repo_name}.db"
    study_name = f"{repo_name}-study"

    study = optuna.create_study(
        direction="maximize",
        storage=storage_url,
        study_name=study_name,
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=seed)
    )

    remaining_trials = max(0, n_trials - len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]))
    if remaining_trials > 0:
        study.optimize(objective, n_trials=remaining_trials)

    if os.path.exists(db_file):
        os.remove(db_file)

    best_trial = study.best_trial
    return best_trial, study

def save_results(repo_name, best_trial, study, seed=None):
    global result_filename

    with open(result_filename, "w") as result_file:
        result_file.write(f"Best trial for {repo_name} repository\n")
        best_k = best_trial.params['alpha']
        best_j = best_trial.params['epsilon']
        unique_traces = int(best_trial.value)
        time = best_trial.user_attrs.get("time", "N/A")

        result_file.write(f"\nBest Trial {best_trial.number}:\n")
        result_file.write(f"Optimal alpha = {best_k:.2f}, Optimal epsilon = {best_j:.2f}\n")
        result_file.write(f"Unique Traces = {unique_traces}, Time = {time} s\n")

        result_file.write(f"\nAll trials for {repo_name}\n\n")
        for trial in study.trials:
            trial_k = trial.params['alpha']
            trial_j = trial.params['epsilon']
            trial_unique_traces = int(trial.value) if trial.value is not None else "N/A"
            trial_time = trial.user_attrs.get("time", "N/A")

            result_file.write(
                f"Trial {trial.number}: alpha = {trial_k:.2f}, epsilon = {trial_j:.2f}, "
                f"Unique Traces = {trial_unique_traces}, Time = {trial_time} s\n"
            )

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 param_tune.py <repo> <sha>")
        sys.exit(1)

    project = sys.argv[1]
    sha = sys.argv[2]
    repo_name = project.split('/')[1]
    result_filename = f"results-{repo_name}.txt"

    best_trial, study = optimize_repo(project, sha, n_trials=100, seed=None)
    save_results(repo_name, best_trial, study, seed=None)
