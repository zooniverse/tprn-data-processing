Take a Zooniverse classifications export and use the Aggregation for Caesar offline tools to get the individual task extracts.

https://github.com/zooniverse/aggregation-for-caesar

For each resulting marking task(s) extracts file we need to convert the pixel coords to geo referenced lat / lon coordinates.

### How to

Firstly assemble the files you need:

https://aggregation-caesar.zooniverse.org/Scripts.html#download-your-data-from-the-project-builder

Use the `TPRN_IN_DATA_DIR` env variable to define the location of the input data on your local filesyste. Likewise the `TPRN_OUT_DATA_DIR` for the output directory.

From the `data_conversion` directory:
You can launch a bash terminal to run all the python commands via `docker-compose run --rm tprn_data bash` and then `python script_name.py` or run them individually as described below.

For detail on the scripts, see https://aggregation-caesar.zooniverse.org/Scripts.html#scripts

1. Verify the install works
    + `docker-compose run --rm tprn_data panoptes_aggregation -h`

0. Configure and extract the classification data for each workflow in the workflows.csv file
    + `docker-compose run --rm tprn_data ./extract_workflows_data.sh inputs/workflows.csv inputs/workflow_contents.csv`
