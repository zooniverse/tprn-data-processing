import subprocess, os, pdb
from panoptes_client import Subject

def last_uploaded_index(upload_state_tracker_path):
    proc_to_find_last_uploaded_index = subprocess.run(["tail", "-n", "1", upload_state_tracker_path], capture_output=True)
    # Proxy for missing file
    # CompletedProcess(args=['tail', '-n', '1', 'outputs/upload_state_tracker.txt'],
    #   returncode=1, stdout=b'',
    #   stderr=b"tail: cannot open 'outputs/upload_state_tracker.txt' for reading: No such file or directory\n"
    #)
    if proc_to_find_last_uploaded_index.returncode == 1:
        # start at the beginning
        print("Starting at the beginning of the manifest file.")
        return 0
    else:
        # file format is index,last_file_name.txt
        tail_output = str(proc_to_find_last_uploaded_index.stdout, 'utf-8')
        last_uploaded_index = int(tail_output.split(',')[0])
        print("Found last loaded index from file.")
        print("Starting at the row %s of the manifest file." % last_uploaded_index)
        return last_uploaded_index

def create_subject(project, metadata, media_files):
    subject = Subject()
    subject.links.project = project
    for media_file in media_files:
        subject.add_location(media_file)
    subject.metadata.update(metadata)
    subject.save()
    return subject

def add_batch_to_subject_set(subject_set, subjects):
    print('Linking {} subjects to the set with id: {}'.format(len(subjects), subject_set.id))
    subject_set.add(subjects)

def handle_batch_failure(saved_subjects):
    print('\nRolling back, attempting to clean up any unlinked subjects.')
    for subject in saved_subjects :
        print('Removing the subject with id: {}'.format(subject.id))
        subject.delete()

def symlink_image(marshal_dir, tiled_data_dir, file_name):
    file_path = "%s/tiles_before_jpg/%s" % (tiled_data_dir, file_name)
    symlink_path = "%s/%s" % (marshal_dir, file_name)
    if not os.path.isfile(symlink_path):
        os.symlink(os.path.abspath(file_path), symlink_path)
    return symlink_path

def remove_symlinks(linked_media_files):
    for symlink_file in linked_media_files:
        # os.path.isfile(symlink_path)
        os.unlink(symlink_file)

# write the index state to the tracker file path
def update_state_tracker(upload_state_tracker_path, index, before_file_name):
    upload_state_tracker_file = open(upload_state_tracker_path, "a")
    upload_state_tracker_file.write("%s,%s\n" % (index, before_file_name))
    upload_state_tracker_file.close()
