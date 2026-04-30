import subprocess
import time
import os
# import threading
from multiprocessing import Process

sha_cnt = 0
log_file = open('log-base.txt', 'a', buffering=1)

projects = [
"agarciadom/xeger,3f2d72baa1ccc0604ff9c9a89830bdbed2c4c6cei,0.01,0.01",
"albfernandez/javadbf,c378f58d773980f7b10e501a4f2ae061cf2d65d8,0.04,0.26",
"almson/almson-refcount,022ee5f5c3f4403be04ced6a8dcd9e9d1572ecad,0.84,0.01", 
"Antibrumm/jackson-antpathfilter,d3114a12ca3c0b8b568d6debf5776bc8d96ffab7,0.21,0.65",
"awslabs/route53-infima,35d5ab221fb8457d8a0611d940a88fb8190bbc37,0.91,0.21",
"romix/java-concurrent-hash-trie-map,24094313b2a372a01bfe4c2dc2ddf9104fc6b5ef,0.42,0.01",
"codelion/gramtest,931f3b46c332c3588d496976ccc652499b9c81c8,0.96,0.99",
"conveyal/osm-lib,3e69d214d131b1d89e5d5fb28100635512dc1138,0.99,0.01",
"cowtowncoder/java-uuid-generator,77175b9dc2ea7c5837fad347f9f633691951e797,0.23,0.19",
"davidmoten/rtree,25703f27d81564ba9e6e0425032b248618dc13ad,0.01,0.10",
"davidmoten/rtree-multi,076f3b3499b1ba85c69d6b50ee54704e8d2509f3,0.49,0.99",
"davidmoten/rtree2,f59676947fd463546259f5a9593161c1f60084d5,0.01,0.08",
"dperezcabrera/jpoker,53ee95ee2f352edb5460900c8633c4ddb9402bda,0.94,0.01",
"f4b6a3/uuid-creator,d4dee8baa6e0e5adf4b10cf1dd3bfe60689b54ac,0.91,0.05",
"ghaffarian/progex,b8c75255305ba45dbcf7d895f81f415375edcd5e,0.96,0.89",
"hlavki/jlemmagen,fbd08c6c289697444762c1458a366329234f9c16,0.99,0.44",
"huaban/jieba-analysis,9885ae31e4af6afba118956c39ef917161ead21e,0.99,0.85",
"lexburner/consistent-hash-algorithm,163e5c7669808d9f310ef9d53385deb4ce6f979b,0.82,0.52",
"MezereonXP/AnomalyDetectTool,8fb7626db097c7c2d668f50bc4ea3561eb4a8186,0.95,0.11",
"mocnik-science/geogrid,6f4d2afe616ec0d1a29a0e5009e95fba2adf6b9d,0.03,0.13",
"renfei/ik-analyzer,d5bcfe7832edeb20db93a579880c84368181d917,0.52,0.26",
"solita/functional-utils,ec9ec4d9b46341c1a3df6e1202328111612cc46e,0.01,0.04",
"StarlangSoftware/TurkishPropBank,b7bc44b88993ecb15828d68e2b9dd09fcf228521,0.50,0.96",
"StarlangSoftware/TurkishSentiNet,ff8974afb88ba6255f331ac743aca106eaf8d332,0.57,0.06",
"Sweetiee-yi/Jaba,9bb88ed6e7d6dd8d387ea1d71676b3fd313ffff3,0.99,0.99",
"wiqer/ef-redis,cbb51e2d38cb1f67ef825285750fdde4062d4384,0.78,0.02",
"zhoujianling/PointCloudUtilities,e61771aadc77787f9469b36de8a5619b1e544de4,0.95,0.10",
"almondtools/stringsearchalgorithms,b940d24c923946871b48904a02a291d2ecdaa9a8,0.01,0.06",
"danieldk/dictomaton,137b391bd3d38b3e44b653612777216f78eeb12f,0.01,0.01",
"davidmoten/bplustree,179d47df60aa097b84714f4a4f52a69d386dd98d,0.98,0.93",
"eightbitjim/cassette-nibbler,6cbb3f6b76b7063e0cf71e51885afb022ff53acb,0.99,0.97",
"flipkart-incubator/databuilderframework,148d2c25820141b7cbc9b8657c074ac2c035bdb3,0.01,0.01",
"Grundlefleck/ASM-NonClassloadingExtensions,35c367e44ac103b5248fa8726883b854c0c37ada,0.74,0.94",
"houbb/sensitive-word,f8bdf1d22ee8d10a31cf607a0c35877297bdba69,0.01,0.01",
"jahlborn/jackcess,19ee157d4a7f8f26ed4950eb18d14721c54bb1a5,0.25,0.99",
"LiveRamp/HyperMinHash-java,f668b03ea3189827be83ed830f76afbdf5b4d488,0.65,0.11",
"myui/btree4j,46f293d77031572cba22ea421597a1a5975ae4e3,0.08,0.91",
"sbesada/java.math.expression.parser,71998f5a8570fcdee1dfa20cff09e53d5176ccec,0.56,0.91",
"asterisk-java/asterisk-java,c86f695617e041d67ad05ca8910fe30aff48cfcf,0.01,0.02",
"attoparser/attoparser,48e6773ce98d1313306bb098a0f7dbf96d686c6d,0.01,0.03",
"ElectronicChartCentre/java-vector-tile,7b4219982cd30a2bce0c392045fadb1524b005a1,0.97,0.27",
"fraunhoferfokus/Fuzzino,19d655811b9c513fd949d8d0e7c99fa195643ee2,0.99,0.02",
"fusion-jena/JaroWinklerSimilarity,fa0506611ea887a94869235f6be6e773b6759a7d,0.07,0.01",
"indeedeng/vowpal-wabbit-java,623aa3f2975cadd5fb7f4e5d7efd1b542075ca76,0.50,0.02",
"dakusui/jcunit,ede4f017916e22bd106d5b4604cb7798abad8027,0.99,0.79",
"octavian-h/time-series-math,1b9b7cd0c467fd9c0a96672c7e71bd0dc42f21b1,0.99,0.98"
]

INSTANCE_TEMPLATE = # VM template name 
PROJECT_ID = # Google Cloud Platform project name 
GCLOUD_BIN = # path to 'gcloud' binary 
ZONE = # zone to use
HOME = # path to $HOME in VM

def run_command(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def run_ssh(vm_name, cmd):
    ssh_cmd = (
        f"{GCLOUD_BIN} compute ssh {vm_name} "
        f"--project={PROJECT_ID} "
        f"--zone={ZONE} "
        f"--command=\"{cmd}\" "
        f"--quiet"
    )
    return run_command(ssh_cmd)

def create_vm(vm_name):
    print(f"Creating VM: {vm_name}", file=log_file)
    cmd = (
        f"{GCLOUD_BIN} compute instances create {vm_name} "
        f"--project={PROJECT_ID} "
        f"--zone={ZONE} "
        f"--source-instance-template={INSTANCE_TEMPLATE} "
        f"--quiet"
    )
    _, stderr, returncode = run_command(cmd)
    if returncode != 0:
        print(f"Error creating VM {vm_name}: {stderr}", file=log_file)
    else:
        print(f"VM {vm_name} created successfully.", file=log_file)

def check_vm_status(vm_name):
    cmd = (
        f"{GCLOUD_BIN} compute instances describe {vm_name} "
        f"--project={PROJECT_ID} "
        f"--zone={ZONE} "
        f"--format='get(status)'"
    )
    stdout, _, returncode = run_command(cmd)
    if returncode != 0:
        return None
    return stdout.strip()

def wait_for_ssh(vm_name, timeout=120, interval=5):
    print(f"[{vm_name}] Waiting for SSH to become available...", file=log_file)
    total_wait = 0
    while total_wait < timeout:
        _, _, returncode = run_ssh(vm_name, "echo SSH ready")
        if returncode == 0:
            print(f"[{vm_name}] SSH is ready.", file=log_file)
            return True;
        time.sleep(interval)
        total_wait += interval
    print(f"[{vm_name}] Timed out waiting for SSH.", file=log_file)
    return False

def start_vm(vm_name):
    print(f"Starting VM: {vm_name}", file=log_file)
    cmd = (
        f"{GCLOUD_BIN} compute instances start {vm_name} "
        f"--project={PROJECT_ID} "
        f"--zone={ZONE} "
        f"--quiet"
    )
    _, stderr, returncode = run_command(cmd)
    if returncode != 0:
        print(f"Error starting VM {vm_name}: {stderr}", file=log_file)
    else:
        print(f"VM {vm_name} started successfully.", file=log_file)

def setup_vm(vm_name, repo, resume=False):
    if not resume:
        print(f"[{vm_name}] Setting up VM", file=log_file)
        cmds = [
            "sudo apt-get install -y git docker.io",
            "sudo systemctl start docker",
            "sudo docker pull softengresearch/tracemop",
            "sudo docker run -dit --name tracemop tracemop:latest /bin/bash",
            "until sudo docker inspect -f '{{.State.Running}}' tracemop 2>/dev/null | grep -q 'true'; do sleep 1; done"
        ]
    else:
        cmds = [
            "sudo docker start tracemop",
            "until sudo docker inspect -f '{{.State.Running}}' tracemop 2>/dev/null | grep -q 'true'; do sleep 1; done"
        ]

    for cmd in cmds:
        _, _, returncode = run_ssh(vm_name, cmd)
        while returncode != 0:
            _, _, returncode = run_ssh(vm_name,cmd)

        print(f"[{vm_name}] Command completed: {cmd}", file=log_file)

    if not resume:
        repo_name = repo.split("/")[1]
        cmd = f"sudo docker exec tracemop bash -c 'git clone https://github.com/{repo}.git /home/tracemop/{repo_name}'"

        _, _, returncode = run_ssh(vm_name, cmd)
        if returncode != 0:
            print(f"[{vm_name}] Failed to clone the target project {repo} into the Docker container.", file=log_file)
            return

        _, _, _ = run_ssh(vm_name, f"mkdir logs-{repo_name}")
        print(f"[{vm_name}] Target project {repo} cloned successfully.", file=log_file)

    print(f"[{vm_name}] VM setup completed.", file=log_file)

def run_ev_exp(vm_name, repo, sha):
    global sha_cnt

    repo_name = repo.split("/")[1]
    results_file = f"results-base/results-{repo_name}-base.txt"
    result_file = open(results_file, "a")

    print(f"[{vm_name}] Running sha: {sha}", file=log_file)

    stdout, stderr, returncode = run_ssh(vm_name, "sudo docker ps --filter 'name=tracemop'")
    if returncode != 0 or "tracemop" not in stdout.strip():
        print(f"[{vm_name}] Docker container 'tracemop' not running.\n{stderr}", file=log_file)
        setup_vm(vm_name, repo, resume=True)

    cmd = f"sudo docker exec tracemop bash -c 'cd /home/tracemop/{repo.split('/')[1]} && git checkout -f {sha}'"
    _, _, returncode = run_ssh(vm_name, cmd)
    if returncode != 0:
        print(f"[{vm_name}] Failed to checkout SHA {sha}.", file=log_file)
        return

    cmd = (
        "sudo docker exec tracemop bash -c '"
        "export PATH=$PATH:/home/tracemop/apache-maven/bin:"
        "/usr/lib/jvm/java-8-openjdk/bin && "
        f"cd /home/tracemop/{repo.split('/')[1]} && mvn clean test-compile'"
    )
    _, _, _ = run_ssh(vm_name, cmd)

    cmd = (
        "sudo docker exec tracemop bash -c '"
        "export PATH=$PATH:/home/tracemop/apache-maven/bin:"
        "/usr/lib/jvm/java-8-openjdk/bin && "
        f"cd /home/tracemop/{repo.split('/')[1]} && mvn surefire:test'"
    )
    start_time = time.time()
    _, _, _ = run_ssh(vm_name, cmd)
    end_time = time.time()
    execution_time_ms = (end_time - start_time) * 1000 

    result_file.write(f"[{sha_cnt}] {sha} [mvn test] Execution time: {execution_time_ms:.2f} ms\n")
    result_file.flush()

    cmd = f"sudo docker exec tracemop bash -c 'rm -rf /home/tracemop/tracemop/scripts/output-{repo_name}'"
    _, _, _ = run_ssh(vm_name, cmd)

    cmd = (
        "sudo docker exec tracemop bash -c '"
        "export PATH=$PATH:/home/tracemop/apache-maven/bin:"
        "/usr/lib/jvm/java-8-openjdk/bin:"
        "/home/tracemop/aspectj-1.9.7/bin && "
        "export CLASSPATH=/home/tracemop/aspectj-1.9.7/lib/aspectjtools.jar:"
        "/home/tracemop/aspectj-1.9.7/lib/aspectjrt.jar:"
        "/home/tracemop/aspectj-1.9.7/lib/aspectjweaver.jar && "
        "cd /home/tracemop/tracemop/scripts && "
        f"bash not_collect_traces.sh {repo} {sha} output-{repo_name}'"
    )
    stdout, _, _ = run_ssh(vm_name, cmd)
    
    cmd = (
        f"sudo docker exec tracemop bash -c "
        f"'cat /home/tracemop/tracemop/scripts/output-{repo_name}/project/violation-counts | wc -l'"
    )
    violation_count = run_ssh(vm_name, cmd)[0].strip()
    print(f"[{vm_name}] Violations count for {sha}: {violation_count}", file=log_file)

    result_file.write(f"{stdout}\n")
    result_file.write(f"[{sha_cnt}] {sha} [javamop] Violations count: {violation_count}\n")
    result_file.flush()

    cmd = (
        f"sudo docker cp tracemop:/home/tracemop/tracemop/scripts/output-{repo_name}/logs logs-{repo_name}/log-javamop-base-{sha}"
    )
    _, _, _ = run_ssh(vm_name, cmd)
    
    cmd = f"sudo docker exec tracemop bash -c 'rm -rf /home/tracemop/tracemop/scripts/output-{repo_name}'"
    _, _, _ = run_ssh(vm_name, cmd)
    
    print(f"[{vm_name}] JavaMOP execution for SHA {sha} completed.", file=log_file)

    cmd = (
        f"sudo docker exec tracemop bash -c '"
        f"export PATH=$PATH:/home/tracemop/apache-maven/bin:"
        f"/usr/lib/jvm/java-8-openjdk/bin:"
        f"/home/tracemop/aspectj-1.9.7/bin && "
        f"export CLASSPATH=/home/tracemop/aspectj-1.9.7/lib/aspectjtools.jar:"
        f"/home/tracemop/aspectj-1.9.7/lib/aspectjrt.jar:"
        f"/home/tracemop/aspectj-1.9.7/lib/aspectjweaver.jar && "
        f"cd /home/tracemop/tracemop/scripts && "
        f"bash collect_traces.sh {repo} {sha} output-{repo_name}'"
    )
    stdout, _, _ = run_ssh(vm_name, cmd)

    cmd = (
        f"sudo docker exec tracemop bash -c "
        f"'tail -n +2 /home/tracemop/tracemop/scripts/output-{repo_name}/all-traces/unique-traces.txt | wc -l'"
    )
    unique_trace_count = run_ssh(vm_name, cmd)[0].strip()
    print(f"[{vm_name}] Unique traces count for {sha}: {unique_trace_count}", file=log_file)

    result_file.write(f"{stdout}\n")
    result_file.write(f"[{sha_cnt}] {sha} [tracemop] Unique traces count: {unique_trace_count}\n")
    result_file.flush()
    
    cmd = (
        f"sudo docker cp tracemop:/home/tracemop/tracemop/scripts/output-{repo_name}/logs logs-{repo_name}/log-tracemop-base-{sha}"
    )
    _, _, _ = run_ssh(vm_name, cmd)
    
    cmd = f"sudo docker exec tracemop bash -c 'rm -rf /home/tracemop/tracemop/scripts/output-{repo_name}'"
    _, _, _ = run_ssh(vm_name, cmd)

    print(f"[{vm_name}] TraceMOP execution for SHA {sha} completed.", file=log_file)

def copy_results(vm_name, repo_name):
    print(f"[{vm_name}] Copying the results", file=log_file)
    os.makedirs("results-base/logs", exist_ok=True)

    cmd = (
        f"{GCLOUD_BIN} compute scp --recurse {vm_name}:{HOME}/logs-{repo_name} "
        f"results-base/logs --project={PROJECT_ID} --zone={ZONE} --quiet"
    )
    _, stderr, returncode = run_command(cmd)
    if returncode != 0:
        print(f"[{vm_name}] Error copying logs to local: {stderr}", file=log_file)
        return

def vm_worker(vm_name, repo, commit_sha):
    global sha_cnt

    repo_name = repo.split("/")[1] 
    sha_file_path = f"Valg/data/shas/shas-{repo_name}.txt"

    with open(sha_file_path, "r") as file:
        shas = file.read().splitlines()
     
    status = check_vm_status(vm_name)
    
    if status is None:
        create_vm(vm_name)
        wait_for_ssh(vm_name)
        setup_vm(vm_name, repo)
    
    while len(shas) > 0:
        status = check_vm_status(vm_name)

        if status == "TERMINATED":
            print(f"VM {vm_name} is TERMINATED. Restarting...", file=log_file)
            start_vm(vm_name)
            wait_for_ssh(vm_name)
            continue

        sha_cnt = sha_cnt + 1 
        run_ev_exp(vm_name, repo, shas.pop(0))

    copy_results(vm_name, repo_name)

def main():
    os.makedirs("results-base", exist_ok=True)
    processes = []

    for project in projects:
        repo, commit_sha, alpha, epsilon = project.split(",")
        repo_name = repo.split("/")[1]

        if "java.math" in repo_name:
            vm_name = "java-math-expression-parser" + "-base"
        else:
            vm_name = repo_name.lower() + "-base"

        p = Process(target=vm_worker, args=(vm_name, repo, commit_sha))
        p.start()
        print(f"Started process for {vm_name} (PID {p.pid})", file=log_file)
        processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("KeyboardInterrupt detected. Terminating all processes...", file=log_file)
        for p in processes:
            p.terminate()
            p.join()

if __name__ == "__main__":
    main()

log_file.close()
