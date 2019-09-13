import pandas
from convert_to_lat_lon import get_lat_coords_from_pixels, get_lon_coords_from_pixels
from panoptes_aggregation.csv_utils import unjson_dataframe
import progressbar
import numpy as np


def extract_to_lat_lon(extract_csv, subject_csv, output_filename):
    extracts = pandas.read_csv(extract_csv)
    subjects = pandas.read_csv(subject_csv)
    # get info about frame, task, and tool numbers from column names
    frame_task_tool_names = sorted(set(
        [
            '.'.join(col.split('.')[1:])[:-2]
            for col in extracts.columns
            if (col.startswith('data.frame')) and (col.endswith('_x') or col.endswith('_y'))]
    ))
    converted_extracts = []
    # evaluate "strings" from any column starting with 'data.'
    unjson_dataframe(extracts)
    # make a progressbar and loop over data
    widgets = [
        'Converting: ',
        progressbar.Percentage(),
        ' ', progressbar.Bar(),
        ' ', progressbar.ETA()
    ]
    pbar = progressbar.ProgressBar(widgets=widgets, max_value=len(extracts))
    counter = 0
    pbar.start()
    for edx, extract in extracts.iterrows():
        # find the subject's metadata
        sdx = subjects.subject_id == extract.subject_id
        subject_metadata = eval(subjects.metadata[sdx].iloc[0])
        # make a copy of the row
        converted_extract = extract.copy()
        # set new rows to all be the same subject_id
        converted_extract.subject_id = 0
        # convert x and y to lon adn lat
        # these must be
        for key in frame_task_tool_names:
            value_x = converted_extract['data.{0}_x'.format(key)]
            value_y = converted_extract['data.{0}_y'.format(key)]
            if (value_x is not np.nan) and (value_y is not np.nan):
                lon = get_lon_coords_from_pixels(value_x, subject_metadata)
                lat = get_lat_coords_from_pixels(value_y, subject_metadata)
                # filter out nan values (these are out of bounds points)
                gdx = np.isfinite(lon) & np.isfinite(lat)
                # convert to lists rather than numpy arrays in order to save as a csv correctly
                converted_extract['data.{0}_x'.format(key)] = lon[gdx].tolist()
                converted_extract['data.{0}_y'.format(key)] = lat[gdx].tolist()
        converted_extracts.append(converted_extract)
        counter += 1
        pbar.update(counter)
    pbar.finish()
    converted_dataframe = pandas.DataFrame(converted_extracts)
    converted_dataframe.to_csv(output_filename)
    return 'done'
