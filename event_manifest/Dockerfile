FROM python:3-stretch

MAINTAINER Zooniverse <contact@zooniverse.org>

WORKDIR /tprn_manifest

RUN pip install --upgrade pip
RUN pip install -U awscli

ADD ./ /tprn_manifest
