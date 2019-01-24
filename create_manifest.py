'''

create_manifest.py takes the before and after tile csv files and combines them to a single
zooniverse upload csv manifest for use by the panoptes cli subject uploader

'''

import sys, os, re, argparse
import pandas as pd
from difflib import SequenceMatcher as SM

parser = argparse.ArgumentParser(description='Create a tiled image data csv manifest to upload subjects to the Zooniverse.')
parser.add_argument('--source', dest='attribution_source', choices=['dg', 'planet', 'sentinel', 'landsat'], required=True)
parser.add_argument('before_csv_infile',help='the before epoch file tile metadata from convert_tiles_to_jpg.py')
parser.add_argument('after_csv_infile', help='the after epoch file tile metadata from convert_tiles_to_jpg.py')
args = parser.parse_args()

before_csv_infile = args.before_csv_infile
after_csv_infile  = args.after_csv_infile
attribution_source  = args.attribution_source

# TODO: fix the YEAR metadata input
if attribution_source == 'dg':
    attribution_text = 'DigitalGlobe Open Data Program - Creative Commons Attribution Non Commercial 4.0'
elif attribution_source == 'planet':
    attribution_text = 'Planet Team ([YEAR]). Planet Application Program Interface: In Space For Life on Earth. San Francisco, CA. https://api.planet.com License: CC-BY-SA'
elif attribution_source == 'sentinel':
    attribution_text = 'Copernicus Sentinel data [Year] for Sentinel data'
elif attribution_source == 'landsat':
    attribution_text = 'USGS/NASA Landsat'
else:
    print("Unknown image data source, muse be one of the --source opts only")
    sys.exit(1)

print("Constructing the before / after manifest upload CSV...")

# use the data dir for outputs from the make tiles as inputs here
tiled_data_dir = os.environ.get('DATA_OUT_DIR','outputs/')

# read both into pandas data frames?
before_manifest_df = pd.read_csv(before_csv_infile)
after_manifest_df = pd.read_csv(after_csv_infile)

# TODO: find a pandas way to compare the set of columns in each data from
for index, row in before_manifest_df.iterrows():
    try:
        after_manifest_row = after_manifest_df.loc[index]
    except KeyError as e:
        print('\nError: files do not match!')
        print('Unknown row %s in after manifest file: %s' % (index, e))
        break

    # check the file names match
    before_prefix, before_suffix = re.split("before", row['tif_file'])
    after_prefix, after_suffix = re.split("after", after_manifest_row['tif_file'])
    tif_file_names_match = (before_prefix == after_prefix) and (before_suffix == after_suffix)

    before_prefix, before_suffix = re.split("before", row['jpg_file'])
    after_prefix, after_suffix = re.split("after", after_manifest_row['jpg_file'])
    fuzzy_prefix_match_ratio = SM(None, before_prefix, after_prefix).ratio()
    # super arbitrary cut off for fuzzy match - look into this further as example input files come in
    # before_prefix = 'palu_2018_09_28_'
    # after_prefix - 'palu_2018_09_29_10_01_'
    # SM(None, before_prefix, after_prefix).ratio() =  0.7894736842105263
    # SM(None, before_prefix, "blargh").ratio() =  0.09090909090909091
    jpg_file_names_match = (fuzzy_prefix_match_ratio > 0.5) and (before_suffix == after_suffix)

    if not (tif_file_names_match and jpg_file_names_match):
        print('\nError: file tiling name parts do not match!')
        print('Tile filenames in manifests for row %s do not match and can not be grouped into 1 subject!' % (index))
        print('%s and %s' % (row['tif_file'], after_manifest_row['tif_file']))
        print('%s and %s' % (row['jpg_file'], after_manifest_row['jpg_file']))
        break

    # The tif files are created by gdal so will exist
    # jpg files are via a shell script using `convert`
    # this program may error, report and continue leaving some missing JPG images
    before_jpg_path = "%s/tiles_before_jpg/%s" % (tiled_data_dir, row['jpg_file'])
    after_jpg_path = "%s/tiles_after_jpg/%s" % (tiled_data_dir, after_manifest_row['jpg_file'])
    jpg_files_exist = os.path.isfile(before_jpg_path) and os.path.isfile(after_jpg_path)
    if not jpg_files_exist:
        print('\nError: missing JPG subject files!')
        print('Check the before file exists: %s' % before_jpg_path)
        print('Check the after file exists: %s' % after_jpg_path)
        break

    # TODO: a much better way of comparing col values
    # cols_to_compare = ['lon_min', 'lon_max', 'lat_min', 'lat_max']
    lon_min_match = row['lon_min'] == after_manifest_row['lon_min']
    lon_max_match = row['lon_max'] == after_manifest_row['lon_max']
    lat_min_match = row['lat_min'] == after_manifest_row['lat_min']
    lat_max_match = row['lat_max'] == after_manifest_row['lat_max']

    geo_cords_match = lon_min_match and lon_max_match and lat_min_match and lat_max_match
    if not geo_cords_match:
        print('\nError: files do not match!')
        print('Geo coords in manifests for row %s have different coords!' % (index))
        break

# All input validations have passed!
# add more in here as they come along

# create the export data frame
prn_zoo_manifest = pd.DataFrame(index=before_manifest_df.index, columns=[])

# create the metadata to show to users
prn_zoo_manifest['jpg_file_before'] = before_manifest_df['jpg_file']
prn_zoo_manifest['jpg_file_after'] = after_manifest_df['jpg_file']
prn_zoo_manifest['tif_file_before'] = before_manifest_df['tif_file']
prn_zoo_manifest['tif_file_after'] = after_manifest_df['tif_file']
prn_zoo_manifest['google_maps_link'] = after_manifest_df['google_maps_link']
prn_zoo_manifest['openstreetmap_link'] = after_manifest_df['openstreetmap_link']
prn_zoo_manifest['attribution'] = attribution_text

# add image scale coords in (put this into the convert_tiles_to_jpg.py script?)
def calculate_km_scale(row, col_name_prefix):
    max_col = '%s_m_max' % col_name_prefix
    min_col = '%s_m_min' % col_name_prefix
    return (row[max_col] - row[min_col]) / 1000

prn_zoo_manifest['x_km'] = before_manifest_df.apply(calculate_km_scale, args=('x'), axis=1)
prn_zoo_manifest['y_km'] = before_manifest_df.apply(calculate_km_scale, args=('y'), axis=1)

# create the metadata that will not be shown to users
#
# Headers that begin with "#" or "//" denote private fields that will not be
#   visible to classifiers in the main classification interface or in the
#   Talk discussion tool.
#
# Headers that begin with "!" denote fields that will not be visible to
#    classifiers in the main classification interface but will be visible
#    after classification in the Talk discussion tool.
#
# https://github.com/zooniverse/Panoptes-Front-End/blob/21cf42485929a62938112d5e2d4bca1a6702b00e/app/pages/lab/subject-set.cjsx#L212

hidden_existing_output_columns = (
    'projection_orig',
    'lat_ctr',
    'lat_max',
    'lat_min',
    'lon_ctr',
    'lon_max',
    'lon_min',
    'x_m_ctr',
    'x_m_max',
    'x_m_min',
    'y_m_ctr',
    'y_m_max',
    'y_m_min',
    'imsize_x_pix',
    'imsize_y_pix',
    'tifsize_x_pix',
    'tifsize_y_pix'
)

for column_name in hidden_existing_output_columns:
    metadata_header = "!%s" % column_name
    prn_zoo_manifest[metadata_header] = before_manifest_df[column_name]

output_manifest_name = "subject_manifest.csv"
csv_manifest_output_path = "%s/%s" % (tiled_data_dir, output_manifest_name)
prn_zoo_manifest.to_csv(csv_manifest_output_path)

print("Wrote before/after subject manifest csv to %s" % csv_manifest_output_path)
