'''

create_pipeline_manifest.py takes user input about a PRN activation event.
This metadata is used to locate and process the source before and after event imagery
to Zooniverse subjects
stored creates a json file

This information includes:
1. Event name and Region of interest (ROI) bounding box coordinates
3. The Zooniverse project for the event repsonse
4. S3 bucket and path details for storing data products created by the PRN pipeline for:
    + Manifest files
    + extracted and formatted raw classifcation data for use by IBCC code
    + IBCC data producs for maps UI
'''

import sys, os, io, json, datetime
from subprocess import Popen, PIPE

def string_to_num(s):
    try:
        return int(s)
    except ValueError:
        return float(s)

def input_header(header, instructions=""):
    print("\n")
    print(header)
    underline = '=' * len(header)
    print(underline)
    print(instructions + '\n')

def event_name(user_supplied):
    underscore = user_supplied.replace(" ", "_")
    return underscore.lower()

def get_bool(prompt):
    while True:
        try:
           return {"y":True,"n":False}[input(prompt).lower()]
        except KeyError:
           print('Invalid input please enter y or n!')

current_dt = datetime.datetime.now()

data = { "manifest_date": current_dt.strftime("%Y/%m/%d") }

input_header("Questions you have to answer for the PRN event")
data['name'] = input('What is the event name the PRN is activating for? ')

event_name = event_name(data['name'])
json_manifest_file_path = 'outputs/%s.json' % event_name
use_existing_manifest = False

manifet_exists = os.path.isfile(json_manifest_file_path)
if manifet_exists:
    print('\nExisting manifest exists at ' + json_manifest_file_path)
    use_existing_manifest = get_bool('Use the existing manifest? ')

if use_existing_manifest:
    with open(json_manifest_file_path, 'r') as f:
        data = json.load(f)
        s3_bucket_name = data['s3_metadata']['bucket_name']
        s3_bucket_path = data['s3_metadata']['bucket_path']
else:
    input_header(
        "Bounding box for the event region of interest",
        'Use https://boundingbox.klokantech.com to get coords'
    )
    west_longitude = string_to_num(input('What is the most westerly bounding longitude coordinate? '))
    south_latitude = string_to_num(input('What is the most southerly bounding latitude coordinate? '))
    east_longitude = string_to_num(input('What is the most easterly bounding longitude coordinate? '))
    north_latitude = string_to_num(input('What is the most northerly bounding latitude coordinate? '))

    # https://wiki.openstreetmap.org/wiki/Bounding_Box
    # bbox = left,bottom,right,top
    data['bounding_box_coords'] = [ west_longitude, south_latitude, east_longitude, north_latitude ]

    input_header("Zooniverse project id")
    zoo_project_id = string_to_num(input('What is the tPRN Zooniverse project id? '))
    data['zooniverse_metadata'] = { "project_id": zoo_project_id }

    input_header("S3 bucket name and path details for this event")
    s3_bucket_name = input('Name of the s3 bucket to store data in? (default to planetary-response-network) ') or "planetary-response-network"
    s3_bucket_path = input("Name of the s3 bucket path to store the PRN event data? (default to %s) " % event_name) or event_name

    data['s3_metadata'] = {
        "bucket_name": s3_bucket_name,
        "bucket_path": s3_bucket_path,
        "bucket_host_name": s3_bucket_name + ".s3.amazonaws.com"
    }

    # write the output data as json file
    with open(json_manifest_file_path, 'w') as f:
        # json.dump(data, f, sort_keys = True, indent = 2, ensure_ascii=False)
        json.dump(data, f, ensure_ascii=False)

s3_upload_location = 's3://' + s3_bucket_name + '/manifests/' + event_name + '.json'

input_header('Upload the manifest to s3')
try:
    if bool(os.environ.get('DRY_UPLOAD', "")):
        s3_cp_cmd = "aws s3 cp --dryrun"
    else:
        s3_cp_cmd = "aws s3 cp"

    cmd = "%s %s %s" % (s3_cp_cmd, json_manifest_file_path, s3_upload_location)

    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    (out,err) = p.communicate()

    if p.returncode == 0:
        print(out.decode())
        print('\nFinished creating the PRN event manifest, go forth and get the data flowing\n')
    else:
        print ('Failed to upload the file to s3')
        print ("'%s' failed, exit-code=%d error = %s" \
               % (cmd, p.returncode, str(err)))
except OSError as e:
    sys.exit("failed to execute program '%s': %s" % (cmd, str(e)))
