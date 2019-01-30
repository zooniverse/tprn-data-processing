FROM python:3-stretch

MAINTAINER Zooniverse <contact@zooniverse.org>

WORKDIR /tprn_data

RUN pip install --upgrade pip
RUN pip install -U panoptes_aggregation ujson

ADD ./ /tprn_manifest
