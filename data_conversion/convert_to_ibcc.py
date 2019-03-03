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

def get_lat_lon_coords_from_pixels(pixel_coords, geo_metadata):
    # ensure the coords are floats
    marks_x = [float(i) for i in pixel_coords['x']]
    marks_y = [float(i) for i in pixel_coords['y']]

    # TODO: look at how we can use other information to determine the
    # lat / lon extents for use t determine the lat / lon from pixel coords
    # attempt to use corner lat lon_max
    # https://github.com/vrooje/Data-digging/blob/1eece78c0f4dfc6b700e3f631d37681b6a8b7bf6/example_scripts/planetary_response_network/caribbean_irma_2017/extract_markings_to1file.py#L242
    # OR conform to what metadata we will use going forward, see the tiling convert_tiles_to_jpg.py

    try:
        the_x = np.array([geo_metadata['x_min'], geo_metadata['imsize_x_pix']], dtype=float)
        the_y = np.array([geo_metadata['y_min'], geo_metadata['imsize_y_pix']], dtype=float)
        the_lon = np.array([geo_metadata['lon_min'], geo_metadata['lon_max']], dtype=float)
        the_lat = np.array([geo_metadata['lat_min'], geo_metadata['lat_max']], dtype=float)
    except KeyError as e:
        # missing data for the converstion to lat / lon
        raise MissingCoordinateMetadata(str(e))

    # setup interpolation functions to get the lat / lon from pixel marks
    # don't throw an error if the coords are out of bounds, but also don't extrapolate
    f_x_lon = interp1d(the_x, the_lon, bounds_error=False, fill_value=(None, None))
    f_y_lat = interp1d(the_y, the_lat, bounds_error=False, fill_value=(None, None))

    lon = f_x_lon(marks_x)
    lat = f_y_lat(marks_y)

    return lon, lat

def get_lat_coords_from_pixels(marks, geo_metadata):
    try:
        the_y = np.array([geo_metadata['y_min'], geo_metadata['imsize_y_pix']], dtype=float)
        the_lat = np.array([geo_metadata['lat_min'], geo_metadata['lat_max']], dtype=float)
    except KeyError as e:
        # missing data for the converstion to lat / lon
        raise MissingCoordinateMetadata(str(e))

    # setup interpolation functions to get the lat / lon from pixel marks
    # don't throw an error if the coords are out of bounds, but also don't extrapolate
    f_y_lat = interp1d(the_y, the_lat, bounds_error=False, fill_value=(None, None))

    return f_y_lat(marks)

def get_lon_coords_from_pixels(marks, geo_metadata):
    try:
        the_x = np.array([geo_metadata['x_min'], geo_metadata['imsize_x_pix']], dtype=float)
        the_lon = np.array([geo_metadata['lon_min'], geo_metadata['lon_max']], dtype=float)
    except KeyError as e:
        # missing data for the converstion to lat / lon
        raise MissingCoordinateMetadata(str(e))

    # setup interpolation functions to get the lat / lon from pixel marks
    # don't throw an error if the coords are out of bounds, but also don't extrapolate
    f_x_lon = interp1d(the_x, the_lon, bounds_error=False, fill_value=(None, None))

    return f_x_lon(marks)

# get the task lables matching a regex from the task list
def get_task_tool_num_and_label_tuples(label_function, regex, headers, known_labels):
    task_lables = []
    # thought, maybe these can be generated using point_extractor_by_frame config files?
    for header in headers:
        matchObj = regex.match(header)
        if matchObj:
            task_key = matchObj.group(1)
            tool_num = matchObj.group(2)
            label_lookup_key = label_function(task_key, tool_num)
            known_labels[label_lookup_key]
            tool_num_name_tuple = (tool_num, known_labels[label_lookup_key])
            task_lables.append(tool_num_name_tuple)

    return task_lables

# find the list of tool nums and labels e.g.
# [(0, 'blockages'), (1, 'floods'), (2, 'shelters'), (3, 'damage')]
def get_unique_point_task_tuples(headers, known_labels):
    # looking for headers that match the data.frame0.T0_tool0_x format
    # only take the x values to avoid double listing
    point_label_re = re.compile('\Adata\.frame0\.(T\d)_tool(\d)_x\Z', re.IGNORECASE)
    label_constructor = lambda task_key, tool_num: "%s.tools.%s.label" % (task_key, tool_num)
    return get_task_tool_num_and_label_tuples(label_constructor, point_label_re, headers, known_labels)

def output_file_path(file_prefix):
    file_name = file_prefix + '_' + str(output_file_suffix) + '.csv'
    return output_data_dir + '/' + file_name

def point_extractor_exclude_headers(headers):
    exclude_headers = []
    exclude_header_re = re.compile('\Adata\.frame.+', re.IGNORECASE)
    for header in headers:
        matchObj = exclude_header_re.match(header)
        if matchObj:
            exclude_headers.append(matchObj.group(0))

    return exclude_headers

# take the first line of the task label
def format_task_label(label):
    label_lines = label.splitlines()
    hyphenated_label = label_lines[0].replace(" ", "-")
    return hyphenated_label.lower()

def point_subtask_label_headers(headers, known_task_labels):
    subtask_labels = []
    subtask_lable_re = re.compile('\Adata\.frame\d\.(.+)_.+(\d)_details\Z', re.IGNORECASE)
    subtask_label_frame_re = re.compile('\Adata\.(frame)(\d)\..+_details\Z', re.IGNORECASE)
    # NOTE: Not sure if there are more than 1 subtasks per tool, if so the 0 key will increment.
    label_constructor = lambda task_key, tool_num: "%s.tools.%s.details.0.question" % (task_key, tool_num)
    for header in headers:
        subtask_label_tuples = get_task_tool_num_and_label_tuples(label_constructor, subtask_lable_re, [header], known_task_labels)
        # skip point headers (subtasks) that don't match the format
        if len(subtask_label_tuples) == 0:
            continue

        matchObj = subtask_label_frame_re.match(header)
        label_frame_prefix = "%s.%s" % (matchObj.group(1), matchObj.group(2))

        _, subtask_question_label = subtask_label_tuples[0]
        formatted_subtask_label = "%s.%s" % (label_frame_prefix, format_task_label(subtask_question_label))
        subtask_labels.append(formatted_subtask_label)

    return subtask_labels

def get_point_task_label_headers(headers, known_labels):
    task_label_headers = []
    point_label_re = re.compile('\Adata\.frame\d\.(T\d)_tool(\d)_[xy]\Z', re.IGNORECASE)
    point_label_frame_re = re.compile('\Adata\.(frame)(\d)\.T\d_tool\d_([xy])\Z', re.IGNORECASE)
    label_constructor = lambda task_key, tool_num: "%s.tools.%s.label" % (task_key, tool_num)
    for header in headers:
        task_label_tuples = get_task_tool_num_and_label_tuples(label_constructor, point_label_re, [header], known_labels)
        # skip point headers (subtasks) that don't match the format
        if len(task_label_tuples) == 0:
            continue

        _, task_label = task_label_tuples[0]

        matchObj = point_label_frame_re.match(header)
        label_frame_prefix = "%s.%s" % (matchObj.group(1), matchObj.group(2))
        label_point_suffix = matchObj.group(3)
        formatted_point_label = "%s.%s-%s" % (label_frame_prefix, format_task_label(task_label), label_point_suffix)
        task_label_headers.append(formatted_point_label)

    return task_label_headers

def add_data_prefix(label):
    return "%s.%s" % ('data', label)

def is_subtask_header(header):
    return header.split("_")[-1] == 'details'

def exists_in_list(value, list):
    len([element for element in list if element == value] != 0)

## Classify point questions
print('Loading point classifications')
classifications_points = pd.read_csv(point_annotations_file)

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
    for subjects_index, row in subjects_chunk.iterrows():
        subjects_dict[row['subject_id']] = ujson.loads(row['metadata'])

print('Files loaded successfully')

print('Converting marking tasks to lat / lon format')

# subject metadata headers for recording original coords
subject_metadata_orig_headers = [
    'lon_min', 'lon_max',
    'lat_min', 'lat_max',
    'imsize_x_pix', 'imsize_y_pix'
]
subject_metadata_headers = ["image_%s" % header for header in subject_metadata_orig_headers]

# get the current incoming headers for reformatting
extract_file_headers = classifications_points.columns.values.tolist()

# point extractor labels don't have labels on them
# https://github.com/zooniverse/aggregation-for-caesar/issues/115
# let's just convert them ourselves to keep the extractor outputs
# consistently formatted as a sparse matrix for points, questions, shortcuts
headers_to_relabel = point_extractor_exclude_headers(extract_file_headers)

# reformat the point task headers to have the task label names
point_task_label_headers = get_point_task_label_headers(headers_to_relabel, task_labels_dict)
point_task_labels_orig = [header for header in headers_to_relabel if not is_subtask_header(header)]

# get the header columns that are't frame point tool marks
base_column_headers = [header for header in extract_file_headers if header not in headers_to_relabel]
# base_header_index_lookup = [(header, formatted_output_headers.index(header)) for header in base_column_headers]

# get the header columns for the point task subtasks
subtask_label_headers = point_subtask_label_headers(extract_file_headers, task_labels_dict)
subtask_label_headers_orig = [header for header in headers_to_relabel if is_subtask_header(header)]

# construct a new list of formatted labels for the output column ordering
formatted_output_headers = base_column_headers \
    + [add_data_prefix(label) for label in point_task_label_headers] \
    + [add_data_prefix(label) for label in subtask_label_headers] \
    + subject_metadata_headers

# construct a list of incoming headers that match the new output header orderings
original_to_output_format_headers = base_column_headers \
    + point_task_labels_orig \
    + subtask_label_headers_orig \
    + subject_metadata_orig_headers

# create an index mapping to lookup extract row column headers to transformed output header columns
original_header_to_output_index_map = { header: index for index, header in enumerate(original_to_output_format_headers) }

points_temp = []

# Iterate through point classifications finding longitude/lattitude equivalents
for i, row in classifications_points.iterrows():
    subject_id = row['subject_id']
    subject_geo_metadata = subjects_dict[subject_id]
    # I am not sure why this is setup this way, to do with origin points?
    # https://github.com/zooniverse/Data-digging/blob/90677ac24681de834caceaa622f61a2fcc3cbbe1/example_scripts/planetary_response_network/caribbean_irma_2017/extract_markings_to1file.py#L564
    subject_geo_metadata['x_min'] = 1
    subject_geo_metadata['y_min'] = 1

    try:
        for (tool, name) in get_unique_point_task_tuples(row.axes[0], task_labels_dict):
            # frames than 0 & 1 (before and after) only right now.
            for frame_num in [0, 1]:
                # find the pixel coords for any marking tool in this frame
                point_task_tool_basename = "\A(data\.frame%s\.T\d_tool%s_)([xy])\Z" % (frame_num, tool)
                point_task_tool_basename_re = re.compile(point_task_tool_basename, re.IGNORECASE)

                # now convert the data from original to new output format
                reformatted_row = [None] * len(original_header_to_output_index_map)
                for row_header, output_index in original_header_to_output_index_map.items():

                    # handle subtasks
                    # if row_header in subtask_label_headers_orig:
                    #     pdb.set_trace()
                        # detail_list = ujson.eval(row[basename + 'details'])
                    #     for j in range(len(lon)):
                    #         detail = list(detail_list[j][0])[0]
                    #         if detail == 'None':
                    #             detail = 'Unspecified'
                    #         else:
                    #             detail = details[int(detail)]
                    # else:
                    # detail = ''

                    # convert the point / subject data we have to the new output format
                    pointToolMatchObj = point_task_tool_basename_re.match(row_header)
                    if pointToolMatchObj:
                        # Load the pixel location data from extracts
                        pixel_coord_values = row[row_header]
                        # skip empty data row values
                        if pd.isnull(pixel_coord_values):
                            # leave the value as the reformatted_row default set above
                            continue

                # TODO: Working on formatting the list of points for each task tool correctly
                # then when we've got a fully formatted new row
                # we can look at splitting it so each multi point entry
                # has it's own row to avoid embedding json arrays, nested data
                # into a single row of csv

                # classificatoin index 13 has point data  to test
                # if i == 13:
                #     pdb.set_trace()

                        # convert from string to json (data is in array format)
                        pixel_coord_values = [float(i) for i in ujson.loads(pixel_coord_values)]
                        # convert the x,y to lat/long coord using subject geo metadata
                        pixel_coord_type = pointToolMatchObj.group(2)
                        if pixel_coord_type == 'x':
                            reformatted_row[output_index] = get_lon_coords_from_pixels(pixel_coord_values, subject_geo_metadata)
                        elif pixel_coord_type == 'y':
                            reformatted_row[output_index] = get_lat_coords_from_pixels(pixel_coord_values, subject_geo_metadata)
                        else:
                            raise ValueError('Unknown pixel coord value type (not x/y) for found %' % row)

                    elif row_header in subject_metadata_orig_headers:
                        reformatted_row[output_index] = subject_geo_metadata[row_header]
                    else:
                        reformatted_row[output_index] = row[row_header]

    except MissingCoordinateMetadata as e:
        # skip the data set conversion for all points
        print("Missing subject metadata: %s\nCan't convert this data set, quiting." % str(e))
        sys.exit(os.EX_DATAERR)

    # store the row once we have reformatted the row into the new column headers
    # this will be used latter to output the newly formatted data

    # TODO: once we are here we can split each multi mark (other) task to multiple rows
    # of data before we insert into the temp list
    # e.g.
    # data.frame1.T0_tool3_details    [[{'2': 1}], [{'2': 1}]]
    # data.frame1.T0_tool3_x          [531.296875, 539.296875]
    # data.frame1.T0_tool3_y                  [326.75, 188.75]
    # would create 2 rows of data with no arrays' nested objects in them

    points_temp.append(reformatted_row)

    if i % 100 == 0:
        # pdb.set_trace()
        print('Rows done: ' + f"{i:,d}", end='\r')

num_points_processed = len(points_temp)
print('Points done: ' + f"{num_points_processed:,d}")

pdb.set_trace()

# use pandas series vs python list appending to dataframe to avoid the conversion costs
# here
points_outfile_df = pd.DataFrame(points_temp, columns=formatted_output_headers)
input_file_name = os.path.basename(point_annotations_file)
output_filename = output_file_path(input_file_name)
points_outfile_df[formatted_output_headers].to_csv(output_filename, index=False)
print(output_filename + ' file created successfully')

## Classify questions, shortcuts and non-answers
# print('Beginning questions, shortcuts and blanks classifications')
#
# classifications_questions = pd.read_csv(question_annotations_file)
# column_names = classifications_questions.columns.values.tolist()
# # classification_id,user_name,user_id,workflow_id,task,created_at,subject_id,extractor,data.10-to-30,data.None,data.aggregation_version,data.more-than-30,data.none,data.ocean-only-no-land,data.unclassifiable-image,data.up-to-10
# base_columns = ['classification_id', 'user_name', 'user_id', 'workflow_id', 'task',
#                 'created_at', 'subject_id', 'extractor','data.aggregation_version']
# column_subject_extras = ['lon_min', 'lon_max', 'lat_min', 'lat_max', 'imsize_x_pix', 'imsize_y_pix']
# print('Files loaded successfully')

# column_questions_extras = ['question', 'label']
# column_questions = column_names + column_questions_extras + column_subject_extras
# questions_included_cols = base_columns + column_questions_extras + column_subject_extras
# questions_temp = []

# column_shortcuts_extras = ['label']
# column_shortcuts = column_names + column_shortcuts_extras + column_subject_extras
# shortcuts_included_cols = base_columns + column_shortcuts_extras + column_subject_extras
# shortcuts_temp = []

# column_blanks = column_names + column_subject_extras
# blanks_included_cols = base_columns + column_subject_extras
# blanks_temp = []
#
# # Iterate through question classifications, consolidating data
# for i, row in classifications_questions.iterrows():
#     subject_id = row['subject_id']
#     markinfo = subjects_dict[subject_id]
#
#     subject_extras = [
#                         markinfo['lon_min'],
#                         markinfo['lon_max'],
#                         markinfo['lat_min'],
#                         markinfo['lat_max'],
#                         markinfo['imsize_x_pix'],
#                         markinfo['imsize_y_pix']
#     ]
#
#     pdb.set_trace()
#
#     # No answer given for any question
#     elif row['data.none'] == 1.00:
#         temp = row.tolist()
#         temp = temp + subject_extras
#         blanks_temp.append
#
#     if i % 100 == 0:
#         print('Questions done: ' + f"{i:,d}", end='\r')
#
# print('Questions done: ' + f"{i:,d}")

# questions_outfile = pd.DataFrame(questions_temp, columns=column_questions)
# filename = output_file_path('data_questions')
# questions_outfile[questions_included_cols].to_csv(filename, index=False)
# print(filename + ' file created successfully')

# shortcuts_outfile = pd.DataFrame(shortcuts_temp, columns=column_shortcuts)
# filename = output_file_path('data_shortcuts')
# shortcuts_outfile[shortcuts_included_cols].to_csv(filename, index=False)
# print(filename + ' file created successfully')

# blanks_outfile = pd.DataFrame(blanks_temp, columns=column_blanks)
# filename = output_file_path('data_blanks')
# blanks_outfile[blanks_included_cols].to_csv(filename, index=False)
# print(filename + ' file created successfully\n')
# print('Finished converting data to IBCC format\n')
