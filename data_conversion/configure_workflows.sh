#!/bin/bash
WORKFLOW_FILE=$1
WORKFLOW_CONTENTS_FILE=$2

if [ -z "$WORKFLOW_FILE" ] || [ -z "$WORKFLOW_CONTENTS_FILE" ]; then
  echo "Please supply a workflow and contents file"
  exit -1
fi
# get the workflow ids as an array
workflow_ids=($(tail -n +2 ${WORKFLOW_FILE} | cut -d',' -f1 | uniq))

CONFIG_DIR="${DATA_OUT_DIR}/configs"
mkdir -p $CONFIG_DIR
# store the configs in outputs
for workflow_id in "${workflow_ids[@]}"
do
  # we can add workflow major / minor version numbers here if needed
  # NOTE if you don't supply a version number it defaults to the max version
  # found in the supplied workflows.csv, we may have to change this behaviour
 panoptes_aggregation config ${WORKFLOW_FILE} $workflow_id -c ${WORKFLOW_CONTENTS_FILE} -d $CONFIG_DIR
done
