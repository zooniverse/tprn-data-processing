FROM python:3-stretch

MAINTAINER Zooniverse <contact@zooniverse.org>

WORKDIR /tprn_data

RUN pip install --upgrade pip
RUN pip install -U ujson
RUN pip install -U git+git://github.com/zooniverse/aggregation-for-caesar.git@seperate-shortcut-tasks

ADD ./ /tprn_manifest
