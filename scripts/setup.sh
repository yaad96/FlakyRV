#!/bin/bash

SCRIPT_DIR=$( cd $( dirname $0 ) && pwd )
VALG_DIR="${SCRIPT_DIR}/Valg"

REPO_URL="github.com/Amazing-Spots/Valg.git"

function clone_repository() {
  echo "Cloning Valg repository"
  pushd ${SCRIPT_DIR}
  git clone https://${REPO_URL}
  popd
}

function build_extension() {
  echo "Building Valg extension"
  pushd ${VALG_DIR}/scripts/javamop-extension
  mvn package
  mkdir -p ${VALG_DIR}/extensions/
  cp target/javamop-extension-1.0.jar ${VALG_DIR}/extensions/
  popd
}

function build_agents() {
  echo "Building Valg agents"
  pushd ${VALG_DIR}/scripts
  echo "Installing track, no stats agent"
  bash install.sh false false # no track, no stats
  bash install.sh true false # track, no stats
  popd
}

function setup() {
  clone_repository
  build_extension
  build_agents
}

setup
