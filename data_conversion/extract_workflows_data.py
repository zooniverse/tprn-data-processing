from panoptes_aggregation.scripts.config_workflow_panoptes import config_workflow
from panoptes_aggregation.scripts.extract_panoptes_csv import extract_csv
from panoptes_aggregation.scripts.reduce_panoptes_csv import reduce_csv
from extract_to_lat_lon import extract_to_lat_lon
from io import StringIO
import pandas
import os

WORKFLOW_FILE = 'workflows.csv'
DATA_OUT_DIR = 'outputs'
DATA_IN_DIR = 'inputs'
EPS_METERS = 50  # clustering size in meters
EPS = EPS_METERS / 78710  # 1 deg ~= 78710 m
MIN_SAMPLES = 3  # number of points needed to form a cluster

config_dir = os.path.join(DATA_OUT_DIR, 'config')
if not os.path.isdir(config_dir):
    os.mkdir(config_dir)
workflow_csv_file = os.path.join(DATA_IN_DIR, WORKFLOW_FILE)
classification_csv_file = os.path.join(DATA_IN_DIR, 'classifications.csv')
subject_csv_file = os.path.join(DATA_IN_DIR, 'subjects.csv')

workflows = pandas.read_csv(workflow_csv_file)
workflow_ids = workflows.workflow_id.unique()
# for this test limit to one workflow
workflow_ids = [12012]

for workflow_id in workflow_ids:
    extractor_config, reducer_configs, task_label_config = config_workflow(
        workflow_csv_file,
        workflow_id,
        output_dir=config_dir
    )
    print('Exporting data from workflow: {0}'.format(workflow_id))
    extract_filenames = extract_csv(
        classification_csv_file,
        StringIO(str(extractor_config)),
        output_dir=DATA_OUT_DIR,
        order=True,
        output_name='workflow_{0}_classifications'.format(workflow_id)
    )
    if len(extract_filenames) > 0:
        point_extracts_filename = [filename for filename in extract_filenames if 'point_extractor_by_frame' in filename][0]
        lat_lon_converstion_filename = 'point_extractor_by_frame_as_lat_lon_{0}.csv'.format(workflow_id)
        lat_lon_csv = os.path.join(DATA_OUT_DIR, lat_lon_converstion_filename)
        print('converting extracts to lat lon')
        extract_to_lat_lon(
            point_extracts_filename,
            subject_csv_file,
            lat_lon_csv
        )
        point_reducer_config = {'reducer_config': [rc for rc in reducer_configs if 'point_reducer_dbscan' in rc][0]}
        # update the reducer config with cluster values
        point_reducer_config['reducer_config']['point_reducer_dbscan']['eps'] = EPS
        point_reducer_config['reducer_config']['point_reducer_dbscan']['min_samples'] = MIN_SAMPLES
        print('reducing extracts as a single subject')
        reduction_filename = reduce_csv(
            lat_lon_csv,
            StringIO(str(point_reducer_config)),
            output_dir=DATA_OUT_DIR,
            filter='first',
            output_name='workflow_{0}_reductions_lat_lon'.format(workflow_id),
            order=True
        )
        print('done with workflow {0}'.format(workflow_id))
