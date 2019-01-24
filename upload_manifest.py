'''

create_manifest.py takes the before and after tile csv files and combines them to a single
zooniverse upload csv manifest for use by the panoptes cli subject uploader

'''

import sys, os, re, argparse, signal
import pandas as pd
import pdb # pdb.set_trace()
from panoptes_client import Panoptes, SubjectSet
from panoptes_client.panoptes import PanoptesAPIException
import uploader

# allow OS env to set a defaultS
default_batch_size = os.environ.get('BATCH_SIZE',10)
default_marshal_dir = os.environ.get('MARSHAL_DIR','marshal_dir')
tiled_data_dir = os.environ.get('DATA_OUT_DIR','outputs/')

parser = argparse.ArgumentParser(description='Create a tiled image data csv manifest to upload subjects to the Zooniverse.')
parser.add_argument('--marshal-dir', dest='marshal_dir', default=default_marshal_dir, help='the directory to marshal the file uploads from')
parser.add_argument('--batch-size', dest='batch_size', default=default_batch_size, help='the number of subjects to attempt to upload at once')
parser.add_argument('--admin-mode', dest='admin_mode', default=False, help='run the Zooniverse CLI in admin mode')
parser.add_argument('--subject-set', dest='subject_set_id', help='the subject set to upload the data to', required=True)
parser.add_argument('manifest_csv_file',help='the path to the subject manifest csv file')

args = parser.parse_args()

manifest_csv_file_path = args.manifest_csv_file
marshal_dir = "%s/%s" % (tiled_data_dir, args.marshal_dir)
batch_size = args.batch_size
admin_mode = args.admin_mode
subject_set_id = args.subject_set_id

# setup access to the Zooniverse API
username = os.environ.get('ZOONIVERSE_USERNAME')
password = os.environ.get('ZOONIVERSE_PASSWORD')
creds_exist = username and password
if not creds_exist:
    print("Missing zooniverse credentials, pass them in as environment variables")
    exit(1)
Panoptes.connect(username=username, password=password, admin=admin_mode)

# setup the tile output paths
if not os.path.exists(marshal_dir):
    os.mkdir(marshal_dir)

# find / create the subject set to upload to
# print("Marshaling the manifest subject file data into directory for uploads...")
subject_set = SubjectSet.find(subject_set_id)
print("Found subject set with id: {} to upload data to.".format(subject_set.id))

manifest_csv_file_df = pd.read_csv(manifest_csv_file_path)

# TODO: find out if we are resuming a previously borked upload
# use a file to indicate this state
upload_state_tracker_path = "%s/%s" % (tiled_data_dir, 'upload_state_tracker.txt')
last_uploaded_index = uploader.last_uploaded_index(upload_state_tracker_path)
# the restartable count of subjects that have been uploaded
uploaded_subjects_count = last_uploaded_index

# hold a list of created but unlinked subject set subjects
saved_subjects = []

# handle (Ctrl+C) keyboard interrupt
def signal_handler(*args):
    print('You pressed Ctrl+C! - attempting to clean up gracefully')
    remaining_subjects_to_link = len(saved_subjects)
    try:
        print("Linking %s remaining uploaded subjects" % remaining_subjects_to_link)
        uploader.add_batch_to_subject_set(subject_set, saved_subjects)
        uploader.update_state_tracker(upload_state_tracker_path, index, row['jpg_file_before'])
        uploader.remove_symlinks(row_media_files)
    except PanoptesAPIException as e:
        print('Failed to link %s remaining subjects' % remaining_subjects_to_link)
        uploader.handle_batch_failure(saved_subjects)
    finally:
        raise SystemExit
#register the handler for interrupt signal
signal.signal(signal.SIGINT, signal_handler)

# symlink all the tiled jpg data to the marshaling dir for uplaod
print("Marshaling the manifest subject file data into directory for uploads...")
for index, row in manifest_csv_file_df.iterrows():
    # skip to where we were up to
    if index <= last_uploaded_index:
        continue

    # before_symlink_path = uploader.symlink_image(marshal_dir, tiled_data_dir, row['jpg_file_before'])
    # after_symlink_path = uploader.symlink_image(marshal_dir, tiled_data_dir, row['jpg_file_after'])

    # TODO: why does the above function leave the after as a broken symlink?
    # [print("%s file exists? %s" % (file, os.path.isfile(file))) for file in row_media_files]
    before_file_path = "%s/tiles_before_jpg/%s" % (tiled_data_dir, row['jpg_file_before'])
    before_symlink_path = "%s/%s" % (marshal_dir, row['jpg_file_before'])
    if not os.path.isfile(before_symlink_path):
        os.symlink(os.path.abspath(before_file_path), before_symlink_path)

    after_file_path = "%s/tiles_after_jpg/%s" % (tiled_data_dir, row['jpg_file_after'])
    after_symlink_path = "%s/%s" % (marshal_dir, row['jpg_file_after'])
    if not os.path.isfile(after_symlink_path):
        os.symlink(os.path.abspath(after_file_path), after_symlink_path)

    # try and handle api failures, intermittent network, etc.
    try:
        # read the pandas series here without the index from row
        # to construct a dict object for use as metadata
        metadata = row[1:-1].to_dict()
        row_media_files = [ before_symlink_path, after_symlink_path ]
        subject = uploader.create_subject(subject_set.links.project, metadata, row_media_files)
        # save the list of subjects to add to the subject set above
        saved_subjects.append(subject)
        # clean up the linked media files
        uploader.remove_symlinks(row_media_files)

    except PanoptesAPIException as e:
        print('\nError occurred on row: {} of the csv file'.format(len(saved_subjects)+1))
        print('Details of error: {}'.format(e))
        uploader.handle_batch_failure(saved_subjects)
        raise SystemExit

    # link each batch of new subjects to the subject set
    if len(saved_subjects) % batch_size == 0:
        uploader.add_batch_to_subject_set(subject_set, saved_subjects)
        uploaded_subjects_count += len(saved_subjects)
        saved_subjects = []

        # TODO: move this to a progress bar
        print("Uploaded and linked {} subjects".format(uploaded_subjects_count))

        uploader.update_state_tracker(upload_state_tracker_path, index, row['jpg_file_before'])


# catch any left over batches in the file
if len(saved_subjects) > 0:
    uploader.add_batch_to_subject_set(subject_set, saved_subjects)
    uploaded_subjects_count += len(saved_subjects)
    # cleanup the state tracker file to ensure we don't replay the last set of data
    os.remove(upload_state_tracker_path)

print("Finished uploading {} subjects".format(uploaded_subjects_count))
