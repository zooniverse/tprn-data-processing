# Event Before and After image tiling scripts
Scripts to help build subjects and deploy Planetary Response Network (PRN) project through the Zooniverse platform.

# Get started

Use docker-compse to run the code and attach your input data to the container
+ `TPRN_IN_DATA_DIR=/your_tpnr_data_dir docker-compose run --rm tprn bash`

if you need to (re)build the container
+ `docker-compose build tprn`

#### Add your local data directory to the docker container
To allow the code to access you data directory you can specify the path via an ENV variable via `TPRN_IN_DATA_DIR=/path/to/tiff/data` either at run time or for your shell session. This directory will be mounted into the running container to the
`/tprn/data/` directory.

To avoid specifying this every time you can setup your local data directory as an environment variable, e.g. `export TPRN_IN_DATA_DIR=/your_tpnr_data_dir`.

If you don't do this you will have to prefix `TPRN_IN_DATA_DIR=/your_tpnr_data_dir` before the docker-compose commands below, e.g.
+ `TPRN_IN_DATA_DIR=/tprn_data/ docker-compose run --rm tprn python make_tiff_tiles.py`

Note: you can also set the data output directory using `TPRN_OUT_DATA_DIR` as well.

All the example scripts below assume you have set this env variable.

# Running the scripts
Run the scripts through docker-compose
+ `docker-compose run --rm tprn python make_tiff_tiles.py`

Alternatively bash into a container and run the scripts interactively
+ `docker-compose run --rm tprn bash`
  + `python make_tiff_tiles.py` at the container prompt


# Tile up the before and after tiffs
*The input TIFF images are should be in the mounted input directory (see docker-compose.yml for more details)*
For each epoch run the following commands:

**Before images**
1. Run *make_tiff_tiles.py* on your **before** input data file
`docker-compose run --rm tprn python make_tiff_tiles.py roi_planet_before.tif before x=500 y=500`
  + Use the output `roi_planet_before.csv` file as an input to the next step
  ```
  FINISHED
  mv outputs/tiles_before_tiff/roi_planet_before.csv outputs
  ... images are tiled and saved to outputs/tiles_before_tiff/
  with tiled image coordinates in roi_planet_before.csv.
  ```
0. Run *convert_tiles_to_jpg.py* on your tiled **before** tiff data
`docker-compose run --rm tprn python convert_tiles_to_jpg.py roi_planet_before.csv before --run`

**After images**
1. Run *make_tiff_tiles.py* on your **after** input data
`docker-compose run --rm tprn python make_tiff_tiles.py roi_planet_after.tif after x=500 y=500`
0. Run *convert_tiles_to_jpg.py* on your tiled tiff data (using the output from step above as the input csv file)
`docker-compose run --rm tprn python convert_tiles_to_jpg.py roi_planet_after.csv after --run`

# Create the before/after subject manifest
+ `docker-compose run --rm tprn python create_manifest.py --source dg outputs/roi_before_extra.csv outputs/roi_after_extra.csv`

# Upload the manifest data to the Zooniverse
+ `docker-compose run --rm tprn python upload_manifest.py --subject-set 1 outputs/subject_manifest.csv`

Marshal the manifest subject data and upload the subjects to the Zooniverse. Should this fail at any point it you can restart it and it will start where it left off.

# Rebuild the conda deps and export the config
Note: most likely not needed right now
+ `docker-compose build tprn-conda-env-build`
+ `docker-compose run --rm tprn-conda-env-build bash`
+ `conda env export > conda_env/tprn.yml`
