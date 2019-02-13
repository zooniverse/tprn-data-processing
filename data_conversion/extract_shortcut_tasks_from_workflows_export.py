import sys, os, argparse
import pandas as pd
import ujson

import pdb

parser = argparse.ArgumentParser(description='Extract the known short cut tasks for a specified workflow and version')
parser.add_argument('--workflows-file', dest='workflows_file', help='the workflows export file', required=True)
parser.add_argument('--workflow-id', type=int, dest='workflow_id', help='the id of the workflow', required=True)
parser.add_argument('--workflow-version-num', type=int, dest='workflow_version_num', help='the workflow version number', required=True)

args = parser.parse_args()

workflows_file = args.workflows_file
workflow_id = args.workflow_id
workflow_version_num = args.workflow_version_num

print('Extracting question shortcuts from workflows file')
workflows_data = pd.read_csv(workflows_file)

shortcut_task_keys = []

for i, row in workflows_data.iterrows():
    if (row['workflow_id'] == workflow_id and row['version'] == workflow_version_num):
        tasks = ujson.loads(row['tasks'])
        for key in tasks.keys():
            task_data = tasks[key]
            if (task_data['type'] == 'shortcut'):
                shortcut_task_keys.append(key)

if len(shortcut_task_keys):
    print(','.join(shortcut_task_keys))
else:
    sys.exit("can't find any shortcut keys")
