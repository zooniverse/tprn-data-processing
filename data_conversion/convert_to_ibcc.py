import sys, os, argparse, time
import numpy as np
import pandas as pd
import ujson
import yaml
import re
from scipy.interpolate import interp1d
import scipy.ndimage
from ast import literal_eval

class MissingCoordinateMetadata(Exception):
    # see tiling/convert_tiles_to_jpg.py
    """Raised when the subject doesn't have the metadata for pixel conversion to lat/lon"""
    pass

import pdb

'''
# Instructions
Extract from raw exports (via Coleman's workflow extractor) to separate flat .csv files with point
selections converted to longitude/latitude from subject metadata (via Brooke's conversion function)

1. Extract data as per https://aggregation-caesar.zooniverse.org/Scripts.html#extracting-data

2. Run
    python convert_to_ibcc.py \
      --points outputs/point_extractor_by_frame_workflow_4970.csv \
      --questions outputs/question_extractor_workflow_4970.csv \
      --subjects inputs/subjects.csv
      --output-suffix 'identifier-file-suffix'

- Where 'point_extractor_by_frame_example.csv' and 'question_extractor_example.csv' are outputs from 1
- And 'subjects_metadata_file.csv' is the metadata of the subjects (images),
containing edge longitude and lattitude and image size
- And 'test' is the desired file suffix

# Output (with 'test' as suffix)
- 'data_points_test.csv': Marks data output
    1. 'tool' -- 0, 1, 2, 3, corresponding to 'label'
    2. 'label' -- 'blockages', 'floods', 'shelters', 'damage' indicating mark type
    3. 'how_damaged' -- 'Minor', 'Moderate', 'Catastrophic' indicating damage amount
    4. 'frame' -- Image on which the point was placed (0: before, 1: after)
    5. 'x' -- x-coordinate of mark in image
    6. 'y' -- y-coordinate of mark in image
    7. 'lon_mark' -- longitude of mark
    8. 'lat_mark' -- latitude of mark

- 'data_questions_test.csv': Structure question output
    1. 't2_approximately_ho__s_your_estimate' -- contains answer to number of structures
    (None, <10, 10-30, >30) as strings

- 'data_shortcuts_test.csv': Shortcuts output
    1. 'label' --  contains 'Unclassifiable Image' if image declared unclassifiable or
    'Ocean Only (no land)' if image declared to contain no land

- 'data_blanks_test.csv': contains the metadata of skipped classfications

- All outputs end with the following subject infomation:
    1. 'lon_min' -- longitude at edge of image
    2. 'lon_max' -- longitude at other edge of image
    3. 'lat_min' -- latitude at edge of image
    4. 'lat_max' -- latitude at other edge of image
    5. 'imsize_x_pix' -- width of image (pixel)
    6. 'imsize_y_pix' -- height of image (pixel)
'''

# TODO: convert these to use parse args or something like it
# avoid the defaults, force the user to supply valid values

default_suffix = time.strftime("%Y%m%d-%H%M%S")

parser = argparse.ArgumentParser(description='Convert extracted data point task annotations to lat / lon format')
parser.add_argument('--points', help='the file containing the extracted point annotations', required=True)
parser.add_argument('--questions', help='the file containing the extracted question annotations', required=True)
parser.add_argument('--subjects', help='the subjects export file containing subject metadata', required=True)
parser.add_argument('--task-labels', dest='task_labels', help='the file containing the workflow version task labels', required=True)
parser.add_argument('--output-suffix', dest='output_suffix', help='a suffix to add to each output file before the extension', default=default_suffix)

args = parser.parse_args()

point_annotations_file = args.points
question_annotations_file = args.questions
subjects_metadata_file = args.subjects
task_labels_file = args.task_labels
output_file_suffix = args.output_suffix

output_dir = os.environ.get('DATA_OUT_DIR','outputs/')
output_data_dir = os.path.join(output_dir, 'ibcc')
if not os.path.exists(output_data_dir):
    os.mkdir(output_data_dir)

def get_lat_lon_coords_from_pixels(markinfo):
    mark_x = [float(i) for i in markinfo['x']]
    mark_y = [float(i) for i in markinfo['y']]

    # TODO: look at how we can use other information to determine the
    # lat / lon extents for use t determine the lat / lon from pixel coords
    # attempt to use corner lat lon_max
    # https://github.com/vrooje/Data-digging/blob/1eece78c0f4dfc6b700e3f631d37681b6a8b7bf6/example_scripts/planetary_response_network/caribbean_irma_2017/extract_markings_to1file.py#L242
    # OR conform to what metadata we will use going forward, see the tiling convert_tiles_to_jpg.py

    try:
        the_x = np.array([markinfo['x_min'], markinfo['imsize_x_pix']], dtype=float)
        the_y = np.array([markinfo['y_min'], markinfo['imsize_y_pix']], dtype=float)
        the_lon = np.array([markinfo['lon_min'], markinfo['lon_max']], dtype=float)
        the_lat = np.array([markinfo['lat_min'], markinfo['lat_max']], dtype=float)
    except KeyError as e:
        # missing data for the converstion to lat / lon
        raise MissingCoordinateMetadata(str(e))


    # don't throw an error if the coords are out of bounds, but also don't extrapolate
    f_x_lon = interp1d(the_x, the_lon, bounds_error=False, fill_value=(None, None))
    f_y_lat = interp1d(the_y, the_lat, bounds_error=False, fill_value=(None, None))

    return f_x_lon(mark_x), f_y_lat(mark_y)

# find the list of tool nums and labels e.g.
# [(0, 'blockages'), (1, 'floods'), (2, 'shelters'), (3, 'damage')]
def get_row_point_task_details(col_headers, known_task_labels):
    point_task_details = []
    # thought, maybe these can be generated using point_extractor_by_frame config files?

    # looking for headers that match the data.frame0.T0_tool0_x format
    # only take the x values to avoid double listing
    point_lable_re = re.compile('\Adata\.frame0.(T\d)_tool(\d)_x', re.IGNORECASE)

    for header in col_headers:
        matchObj = point_lable_re.match(header)
        if matchObj:
            task_key = matchObj.group(1)
            tool_num = matchObj.group(2)
            label_lookup_key = "%s.tools.%s.label" % (task_key, tool_num)
            known_task_labels[label_lookup_key]
            tool_num_name_tuple = (tool_num, known_task_labels[label_lookup_key])

            point_task_details.append(tool_num_name_tuple)

    return point_task_details

def output_file_path(file_prefix):
    file_name = file_prefix + '_' + str(output_file_suffix) + '.csv'
    return output_data_dir + '/' + file_name

## Classify point questions
print('Loading point classifications')
classifications_points = pd.read_csv(point_annotations_file)
column_names = classifications_points.columns.values.tolist()
# classification_id,user_name,user_id,workflow_id,task,created_at,subject_id,extractor,data.aggregation_version,
# data.frame{1/0}.T0_tool{3/2/1/0}_{x/y/details} (x18)
base_columns = ['classification_id', 'user_name', 'user_id', 'workflow_id', 'task', 'created_at',
                'subject_id', 'extractor','data.aggregation_version']

# Load up the task labels data from aggregation config
print('Loading the task labels file')
task_labels_dict = {}
with open(task_labels_file) as f:
    task_labels_dict = yaml.safe_load(f)

# Target for optimization here, projects with lots of subjects will make this slow
# for each extraction run, either subset out the data for target classifications
# or do this filtering once and store for each subsequent run
print('Loading the subject data')
subjects_dict = {}
# Make subject dictionary with id as key and metadata
# keep ram down use cols of interest and chunks
chunksize = 10 ** 6
for subjects_chunk in pd.read_csv(subjects_metadata_file, usecols=['subject_id', 'metadata'], chunksize=chunksize):
    for index, row in subjects_chunk.iterrows():
        subjects_dict[row['subject_id']] = ujson.loads(row['metadata'])

print('Files loaded successfully')

print('Converting marking tasks to lat / lon format')
column_points_extras = ['tool', 'label', 'how_damaged', 'frame', 'x', 'y', 'lon_mark', 'lat_mark',
 'lon_min', 'lon_max', 'lat_min', 'lat_max', 'imsize_x_pix', 'imsize_y_pix']
column_points = column_names + column_points_extras
points_included_cols = base_columns + column_points_extras
points_temp = []

# Iterate through point classifications finding longitude/lattitude equivalents
for i, row in classifications_points.iterrows():
    subject_id = row['subject_id']
    markinfo = subjects_dict[subject_id]
    markinfo['x_min'] = 1 #np.ones_like(markinfo['x'])
    markinfo['y_min'] = 1 #np.ones_like(markinfo['y'])

    try:
        for (tool, name) in get_row_point_task_details(row.axes[0], task_labels_dict):
            # frames than 0 & 1 (before and after) only right now.
            for df in [0, 1]:
                #data.frame{1,0}.T0_tool{0,1,2,3}_{x,y}

                basename = 'data.frame' + str(df) + '.T0_tool' + str(tool) + '_'

                try:
                    # Load the pixel location data from extracts
                    markinfo['x'] = ujson.loads(row[basename + 'x'])
                    markinfo['y'] = ujson.loads(row[basename + 'y'])
                except:
                    markinfo['x'] = None
                    markinfo['y'] = None
                    # make sure we try the next frame of data
                    # as the user may have marked the 2nd frame
                    continue

                (lon, lat) = get_lat_lon_coords_from_pixels(markinfo)

                for j in range(len(lon)):
                    add_temp = []
                    if tool == 3: #Tool 3 is Structural damage which can also include further details
                        detail_list = ujson.loads(row[basename + 'details'])
                        for j in range(len(lon)):
                            detail = list(detail_list[j][0])[0]
                            if detail == 'None':
                                detail = 'Unspecified'
                            else:
                                detail = details[int(detail)]
                    else:
                        detail = ''
                    # Append order: 'tool', 'label', 'how_damaged', 'frame', 'x', 'y',
                    #               'lon_mark', 'lat_mark', 'lon_min', 'lon_max', 'lat_min',
                    #               'lat_max', 'imsize_x_pix', 'imsize_y_pix'
                    add_temp = [
                                tool,
                                name,
                                detail,
                                df,
                                markinfo['x'][j],
                                markinfo['y'][j],
                                lon[j],
                                lat[j],
                                markinfo['lon_min'],
                                markinfo['lon_max'],
                                markinfo['lat_min'],
                                markinfo['lat_max'],
                                markinfo['imsize_x_pix'],
                                markinfo['imsize_y_pix']
                    ]
                    temp = row.tolist()
                    temp = temp + add_temp
                    points_temp.append(temp)

        if i % 100 == 0:
            print('Points done: ' + f"{i:,d}", end='\r')

    except MissingCoordinateMetadata as e:
        # skip the data set conversion for all points
        print("Missing subject metadata: %s\nCan't convert this data set, quiting." % str(e))
        sys.exit(os.EX_DATAERR)

num_points_processed = len(points_temp)
print('Points done: ' + f"{num_points_processed:,d}")

points_outfile = pd.DataFrame(points_temp, columns=column_points)
filename = output_file_path('data_points')
points_outfile[points_included_cols].to_csv(filename, index=False)
print(filename + ' file created successfully')

## Classify questions, shortcuts and non-answers
print('Beginning questions, shortcuts and blanks classifications')

classifications_questions = pd.read_csv(question_annotations_file)
column_names = classifications_questions.columns.values.tolist()
# classification_id,user_name,user_id,workflow_id,task,created_at,subject_id,extractor,data.10-to-30,data.None,data.aggregation_version,data.more-than-30,data.none,data.ocean-only-no-land,data.unclassifiable-image,data.up-to-10
base_columns = ['classification_id', 'user_name', 'user_id', 'workflow_id', 'task',
                'created_at', 'subject_id', 'extractor','data.aggregation_version']
column_subject_extras = ['lon_min', 'lon_max', 'lat_min', 'lat_max', 'imsize_x_pix', 'imsize_y_pix']
print('Files loaded successfully')

column_questions_extras = ['question', 'label']
column_questions = column_names + column_questions_extras + column_subject_extras
questions_included_cols = base_columns + column_questions_extras + column_subject_extras
questions_temp = []

column_shortcuts_extras = ['label']
column_shortcuts = column_names + column_shortcuts_extras + column_subject_extras
shortcuts_included_cols = base_columns + column_shortcuts_extras + column_subject_extras
shortcuts_temp = []

column_blanks = column_names + column_subject_extras
blanks_included_cols = base_columns + column_subject_extras
blanks_temp = []

# Iterate through question classifications, consolidating data
for i, row in classifications_questions.iterrows():
    subject_id = row['subject_id']
    markinfo = subjects_dict[subject_id]

    subject_extras = [
                        markinfo['lon_min'],
                        markinfo['lon_max'],
                        markinfo['lat_min'],
                        markinfo['lat_max'],
                        markinfo['imsize_x_pix'],
                        markinfo['imsize_y_pix']
    ]

    pdb.set_trace()

    # Get the question answers labels to find the
    # Number of structures visible
    if row['data.None'] == 1.00:
        temp = row.tolist()
        temp.append('t2_approximately_ho__s_your_estimate')
        temp.append('None')
        temp = temp + subject_extras
        questions_temp.append(temp)
    elif row['data.up-to-10'] == 1.00:
        temp = row.tolist()
        temp.append('t2_approximately_ho__s_your_estimate')
        temp.append('<10')
        temp = temp + subject_extras
        questions_temp.append(temp)
    elif row['data.10-to-30'] == 1.00:
        temp = row.tolist()
        temp.append('t2_approximately_ho__s_your_estimate')
        temp.append('10-30')
        temp = temp + subject_extras
        questions_temp.append(temp)
    elif row['data.more-than-30'] == 1.00:
        temp = row.tolist()
        temp.append('t2_approximately_ho__s_your_estimate')
        temp.append('>30')
        temp = temp + subject_extras
        questions_temp.append(temp)

    # ?? How do we determine the shortcut tasks?
    # ?? inspect the workflows source file for id / version?
    #
    # Shortcuts (no answer to any questions)
    elif row['data.unclassifiable-image'] == 1.00:
        temp = row.tolist()
        temp.append('Unclassifiable Image')
        temp = temp + subject_extras
        shortcuts_temp.append(temp)
    elif row['data.ocean-only-no-land'] == 1.00:
        temp = row.tolist()
        temp.append('Ocean Only (no land)')
        temp = temp + subject_extras
        shortcuts_temp.append(temp)

    # No answer given
    elif row['data.none'] == 1.00:
        temp = row.tolist()
        temp = temp + subject_extras
        blanks_temp.append

    if i % 100 == 0:
        print('Questions done: ' + f"{i:,d}", end='\r')

print('Questions done: ' + f"{i:,d}")

questions_outfile = pd.DataFrame(questions_temp, columns=column_questions)
filename = output_file_path('data_questions')
questions_outfile[questions_included_cols].to_csv(filename, index=False)
print(filename + ' file created successfully')

shortcuts_outfile = pd.DataFrame(shortcuts_temp, columns=column_shortcuts)
filename = output_file_path('data_shortcuts')
shortcuts_outfile[shortcuts_included_cols].to_csv(filename, index=False)
print(filename + ' file created successfully')

blanks_outfile = pd.DataFrame(blanks_temp, columns=column_blanks)
filename = output_file_path('data_blanks')
blanks_outfile[blanks_included_cols].to_csv(filename, index=False)
print(filename + ' file created successfully\n')
print('Finished converting data to IBCC format\n')
