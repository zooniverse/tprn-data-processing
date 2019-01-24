Use a pre defined manifest to contain metadata about a PRN response event and to configure a data processing pipeline.

Each manifest will contain information about the PRN activation event, specifically:
1. Activation event metadata
0. The source imagery information to tile and upload event subjects to a Zooniverse PRN subject set.
0. Zooniverse project metadata
0. S3 bucket information for event data products

### How to create an event manifest?

From the `event_manifest` directory:

1. `docker-compose run --rm tprn_manifest python create_event_manifest.py`

0. Read and answer the questions on the prompt, once it's finished the manifest is uploaded to s3 at a pre-defined location based on the name (choose wisely). This location will be reported at the end of the script run.

### Example manifest
```
{
	"manifest_date": "2019/01/09",
	"name": "Dominca 2018",
	"bounding_box_coords": [-61.577664, 15.185255, -61.143342, 15.673547],
	"geotiff_source_imagery": {
		"before_image_file_name": "dominica_planet_before.tif",
		"before_image_provider": "dg",
		"after_image_file_name": "dominica_planet_after.tif",
		"after_image_provider": "dg"
	},
	"zooniverse_metadata": {
		"project_id": 2419,
		"subject_set_id": 60320
	},
	"s3_metadata": {
		"bucket_name": "planetary-response-network",
		"bucket_path": "dominca_2018",
		"bucket_host_name": "planetary-response-network.s3.amazonaws.com"
	}
}
```
