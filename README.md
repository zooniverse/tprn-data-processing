# tPRN-scripts
Scripts to help build subjects and deploy Planetary Response Network (PRN) project through the Zooniverse platform.

Heavily inspired by the work in https://github.com/vrooje/PRN-scripts

# Get started

This repository is responsible for different parts of the tPRN data pipeline lifecycle. From setting up event metadata manifests, to tiling images to Zooniverse subjects. Each separate component is located in a subfolder with their own README detailing how to use them

+  [Event Manifest](event_manifest/) for details on how to setup an event manifest that describes the event the PRN is responding to.

+  [Tiling](tiling/) for details on tiling pre and post event imagery as Zooniverse Subjects
    + You will have to provide the source before and after event imagery. This is manually created (currently), see the followin document for details https://docs.google.com/document/d/1QveOh74QpxEIhxx--7t9Swahe2BmG5yBBtqhSRtLLUk

+ [Data Conversion](data_conversion/) for details on extracting the classification data into a useable format for IBCC / downstream collaborators in the PRN data pipeline.
