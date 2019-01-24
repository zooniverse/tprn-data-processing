'''

convert_tiles_to_jpg is for converting tiles made with make_tiff_tiles into jpgs. It also pulls the tile coordinate information from the csv file exported by make_tiff_tiles.py and adds further columns to it, for manifest creation.



'''

import sys, os
import numpy as np
import pandas as pd
import ujson
import scipy.interpolate
import scipy.ndimage
from osgeo import gdal, osr
from pyproj import Proj, transform
#import urllib
#from PIL import ImageFile
from PIL import Image


try:
    infile = sys.argv[1]
except:
    #infile = "test_gdal_retile_output.csv"
    print("\nUsage: %s gdal_retile_output.csv which_epoch" % sys.argv[0])
    print("      gdal_retile_output is a CSV file that's the result of gdal_retile")
    print("      which_epoch is either \"before\" or \"after\".")
    print("  Optional extra inputs (no spaces):")
    print("    cparams=\"convert params\"")
    print("       parameters to feed into imagemagick convert command (in addition to epoch label)")
    print("    proj=epsg:32620")
    print("       specify the projection rather than get it from a sample file (use with great caution)")
    print("    --run")
    print("       if you actually want to make the jpegs and not just generate a script to do so")
    sys.exit(0)


try:
    before_or_after = sys.argv[2]
except:
    exit_program("ERROR: Must specify which epoch (before/after) - and you should triple-check this!")

epoch_l = before_or_after.lower()
epoch_t = before_or_after.capitalize()

# use the data dir for outputs from the make tiles as inputs here
tiled_data_dir = os.environ.get('DATA_OUT_DIR','outputs/')
tiledir_tiff  = "%s/tiles_%s_tiff" % (tiled_data_dir, epoch_l)
tiledir_jpg  = "%s/tiles_%s_jpg" % (tiled_data_dir, epoch_l)

outfile_extra = "%s/%s" % (tiled_data_dir, infile.replace(".csv", "_extra.csv"))
outfile_jpgsh =  "%s/%s" % (tiled_data_dir, infile.replace(".csv", "_makejpg.sh"))

# setup the tile output paths
if not os.path.exists(tiledir_jpg):
    os.mkdir(tiledir_jpg)

cparams = ''
run_maketiles = False
projection_in = 'epsg:32620'
user_proj     = False

# check for other command-line arguments
if len(sys.argv) > 3:
    # if there are additional arguments, loop through them
    for i_arg, argstr in enumerate(sys.argv[3:]):
        arg = argstr.split('=')

        if arg[0] == "cparams":
            cparams = arg[1]
        elif arg[0] == "proj":
            projection_in = arg[1]
            user_proj = True
        elif arg[0] == "--run":
            run_maketiles = True


convert_params = "%s -gravity south -stroke \"#000C\" -font Arial -pointsize 16 -strokewidth 3 -annotate 0 \"%s\" -stroke none -fill white -annotate 0 \"%s\"" % (cparams, epoch_t, epoch_t)

print("jpg convert params: \n%s\n" % convert_params)

magfac = 2**convert_params.count("-magnify")

# allow the user to specify the default map zoom in the subject metadata
# for high-res imaging like DigitalGlobe - 17
# for medium stuff like Planet Labs - 15
# for lower-res (~10 m) - 13
mapzoom = os.environ.get('SUBJECT_METADATA_MAP_ZOOM',15)


def get_projection(imgfile):
    # ideally we'd just take a single image filename, read the tif file, and figure out the projection string
    try:
        inDS = gdal.Open(imgfile)
        inSRS_wkt = inDS.GetProjection()  # gives SRS in WKT
        inSRS_converter = osr.SpatialReference()  # makes an empty spatial ref object
        inSRS_converter.ImportFromWkt(inSRS_wkt)  # populates the spatial ref object with our WKT SRS
        inSRS_forPyProj = inSRS_converter.ExportToProj4()  # Exports an SRS ref as a Proj4 string usable by PyProj
        #print(inSRS_forPyProj)
        return inSRS_forPyProj, Proj(inSRS_forPyProj)
    except:
        print(" Can't determine projection from images -- assuming something")
        # for now let's just return the same projection for everything
        # this is for Sentinel 2
        proj_fallback = 'epsg:32620'
        return proj_fallback, Proj(init=proj_fallback)


# takes a single metadata row
def get_corner_latlong(metadata, inProj, outProj):
    x_m_min = metadata[1]['x_m_min']
    x_m_max = metadata[1]['x_m_max']
    y_m_min = metadata[1]['y_m_min']
    y_m_max = metadata[1]['y_m_max']

    lon_min, lat_min = transform(inProj,outProj,x_m_min,y_m_min)
    lon_max, lat_max = transform(inProj,outProj,x_m_max,y_m_max)

    return lon_min, lon_max, lat_min, lat_max


def getsizes_local(imagefile):
    # get image size in pixels
    theimg = Image.open("%s/%s" % (tiledir_tiff, imagefile))
    thesize = theimg.size
    theimg.close()
    return thesize

def get_gmaps(row):
    lon_ctr = row[1]['lon_ctr']
    lat_ctr = row[1]['lat_ctr']
    return "https://www.google.com/maps/@%.7f,%.7f,%dz" % (lat_ctr, lon_ctr, mapzoom)

def get_osm(row):
    lon_ctr = row[1]['lon_ctr']
    lat_ctr = row[1]['lat_ctr']
    return "http://www.openstreetmap.org/#map=%d/%.7f/%.7f" % (mapzoom, lat_ctr, lon_ctr)


# if you're supplying anything with a colon like 'epsg:32619', you need init=.
# if you are supplying something more like '+proj=utm +zone=19 +datum=WGS84 +units=m +no_defs ', which comes from e.g. gdal, using init= will crash things
# even though those two strings represent the same projection
# what fun this is
try:
    inProj  = Proj(projection_in)
except:
    inProj  = Proj(init=projection_in)

# this is standard lat and lon
outProj = Proj(init='epsg:4326')

infile_path = "%s/%s" % (tiled_data_dir, infile)
tileparams = pd.read_csv(infile_path, header=None)
# the output doesn't have a header automatically but we know what the parameters are
# the output format is set by gdal_retile so unless that version changes, this shouldn't change
#st_thomas_before_1_1.tif,285000.,289796.347102,2036082.130910,2041000.
colnames = 'tif_file x_m_min x_m_max y_m_min y_m_max'.split()
tileparams.columns = colnames

# if the projection isn't supplied by the user, try to figure it out based on the first file
if not user_proj:
    first_file_name = tileparams.tif_file.head(1)[tileparams.tif_file.index[0]]
    first_file_path = "%s/%s" % (tiledir_tiff, first_file_name)
    projection_in, inProj = get_projection(first_file_path)

tileparams['x_m_ctr'] = 0.5*(tileparams['x_m_min'] + tileparams['x_m_max'])
tileparams['y_m_ctr'] = 0.5*(tileparams['y_m_min'] + tileparams['y_m_max'])
tileparams['projection_orig'] = [projection_in for q in tileparams.x_m_min]

tileparams['jpg_file'] = [q.replace(".tif", ".jpg") for q in tileparams['tif_file']]

coords = [get_corner_latlong(q, inProj, outProj) for q in tileparams.iterrows()]

tileparams['lon_min'] = [q[0] for q in coords]
tileparams['lon_max'] = [q[1] for q in coords]
tileparams['lat_min'] = [q[2] for q in coords]
tileparams['lat_max'] = [q[3] for q in coords]

tileparams['lon_ctr'] = 0.5*(tileparams['lon_min'] + tileparams['lon_max'])
tileparams['lat_ctr'] = 0.5*(tileparams['lat_min'] + tileparams['lat_max'])

print("Fetching image sizes...")
sizes = [getsizes_local(q) for q in tileparams.tif_file]
tileparams['tifsize_x_pix'] = [q[0] for q in sizes]
tileparams['tifsize_y_pix'] = [q[1] for q in sizes]
tileparams['imsize_x_pix'] = magfac * tileparams['tifsize_x_pix']
tileparams['imsize_y_pix'] = magfac * tileparams['tifsize_y_pix']

tileparams['google_maps_link'] = [get_gmaps(q) for q in tileparams.iterrows()]
tileparams['openstreetmap_link'] = [get_osm(q) for q in tileparams.iterrows()]

tileparams.to_csv(outfile_extra)
print("Wrote new csv with extra columns to %s" % outfile_extra)
print("  Now writing script to convert to jpg...")


fout = open(outfile_jpgsh, "w")
for i, row in enumerate(tileparams.iterrows()):
    fout.write("convert %s/%s %s %s/%s\n" % (tiledir_tiff, row[1]['tif_file'], convert_params, tiledir_jpg, row[1]['jpg_file']))
fout.close()

print("  ... script written to %s ." % outfile_jpgsh)

mktile_cmd = "sh < %s" % outfile_jpgsh

if run_maketiles:
    os.system(mktile_cmd)
else:
    print("You may want to run:\n%s" % mktile_cmd)

#bye
