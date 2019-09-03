FROM python:3-stretch

MAINTAINER Zooniverse <contact@zooniverse.org>

WORKDIR /tprn_data

RUN pip install --upgrade pip
RUN pip install -U ujson
RUN pip install -U panoptes_aggregation

ADD ./ /tprn_manifest
