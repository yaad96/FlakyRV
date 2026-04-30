#!/bin/bash
#
# Run Valg without trace-collection
# Usage: bash not_collect_traces.sh <repo> <sha> <output-dir> [timed: false] [stats: false] [save-to-file: true] [path-to-javamop-extension]
#
SCRIPT_DIR=$( cd $( dirname $0 ) && pwd )

REPO=$1
SHA=$2
OUTPUT_DIR=$3
TIMED=${4:-false}
STATS=${5:-false}
SAVE_TO_FILE=${6:-true}
PATH_TO_EXTENSION=$7
PROJECT_NAME=$(echo ${REPO} | tr / -)

ALREADY_CHECKED=false

if [[ -z ${OUTPUT_DIR} ]]; then
  echo "Usage: bash not_collect_traces.sh <repo> <sha> <output-dir> [timed: false] [stats: false] [save-to-file: true] [path-to-javamop-extension]"
  exit 1
else
  if [[ ! ${OUTPUT_DIR} =~ ^/.* ]]; then
    OUTPUT_DIR=${SCRIPT_DIR}/${OUTPUT_DIR}
  fi

  if [[ -n ${PATH_TO_EXTENSION} ]]; then
    if [[ ! ${PATH_TO_EXTENSION} =~ ^/.* ]]; then
      PATH_TO_EXTENSION=${SCRIPT_DIR}/${PATH_TO_EXTENSION}
    fi
  else
    PATH_TO_EXTENSION=${SCRIPT_DIR}/../extensions/javamop-extension-1.0.jar
  fi

  mkdir -p ${OUTPUT_DIR}/logs
fi

function clone() {
  if [[ -d ${OUTPUT_DIR}/project ]]; then
    ALREADY_CHECKED=true
    pushd ${OUTPUT_DIR}/project &> /dev/null
    return 0
  fi
    
  echo "[OK] Cloning project ${REPO}"
  pushd ${OUTPUT_DIR} &> /dev/null
  git clone https://github.com/${REPO} project &> ${OUTPUT_DIR}/logs/clone.log
  if [[ $? -ne 0 ]]; then
    echo "[ERROR] Unable to clone project ${REPO}"
    exit 1
  fi
  pushd project &> /dev/null
  git checkout ${SHA} &>> ${OUTPUT_DIR}/logs/clone.log
}

function install() {
  if [[ ${STATS} == "true" ]]; then
    (time mvn -Dmaven.repo.local=${OUTPUT_DIR}/repo install:install-file -Dfile=${SCRIPT_DIR}/no-track-no-stats-agent.jar -DgroupId="javamop-agent" -DartifactId="javamop-agent" -Dversion="1.0" -Dpackaging="jar") &>> ${OUTPUT_DIR}/logs/install.log
  else
    (time mvn -Dmaven.repo.local=${OUTPUT_DIR}/repo install:install-file -Dfile=${SCRIPT_DIR}/no-track-no-stats-agent.jar -DgroupId="javamop-agent" -DartifactId="javamop-agent" -Dversion="1.0" -Dpackaging="jar") &>> ${OUTPUT_DIR}/logs/install.log
  fi
  if [[ $? -ne 0 ]]; then
    echo "[ERROR] Unable to install agent"
    exit 1
  fi
}

function initial_test() {
  if [[ ${ALREADY_CHECKED} == "true" ]]; then
    return 0
  fi

  (time mvn test-compile -Dmaven.repo.local=${OUTPUT_DIR}/repo -Dsurefire.exitTimeout=86400 -Dmaven.ext.class.path=${PATH_TO_EXTENSION}) &> ${OUTPUT_DIR}/logs/compile.log
  if [[ ${TIMED} == "true" ]]; then
    echo "[OK] Running surefire:test once to download dependency"
    export ADD_AGENT=0
    (time mvn surefire:test -Dmaven.repo.local=${OUTPUT_DIR}/repo -Dsurefire.exitTimeout=86400 -Dmaven.ext.class.path=${PATH_TO_EXTENSION}) &> ${OUTPUT_DIR}/logs/initial-test.log
    local status=$?
    if [[ ${status} -ne 0 ]]; then
      echo "[ERROR] Unable to run test (initial)"
      exit 1
    fi
    unset ADD_AGENT
  fi
}

function mop() {
  export MAVEN_OPTS="-Xmx500g -XX:-UseGCOverheadLimit"
  if [[ ${SAVE_TO_FILE} == "true" ]]; then
    export RVMLOGGINGLEVEL=UNIQUE
  fi

  echo "[OK] Running MOP"
  local start=$(date +%s%3N)
  (time mvn surefire:test -Dmaven.repo.local=${OUTPUT_DIR}/repo -Dsurefire.exitTimeout=86400 -Dmaven.ext.class.path=${PATH_TO_EXTENSION}) &> ${OUTPUT_DIR}/logs/mop.log
  local status=$?
  
  if [[ ${status} -ne 0 ]]; then
    echo "[ERROR] Unable to run MOP"
    exit 1
  fi
  local end=$(date +%s%3N)
  local duration=$((end - start))
  echo "[OK] Duration: ${duration} ms"
  
  popd &> /dev/null # back to ${OUTPUT_DIR}
  popd &> /dev/null # back to CWD
}

clone
install
initial_test
mop
echo "OK!"
