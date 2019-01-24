FROM continuumio/anaconda:5.2.0

MAINTAINER Zooniverse <contact@zooniverse.org>

WORKDIR /tprn

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        imagemagick \
        && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN mkdir -p data

ADD conda_env/tprn.yml /tprn

# use the existing conda env for deps
RUN conda env create -f tprn.yml

# allow the conda env to run via bash
RUN echo "source activate tprn" > ~/.bashrc

# activate the created tprn environment from the yaml file
ENV PATH /opt/conda/envs/tprn/bin:$PATH

RUN pip install --upgrade pip
# switch to the released client >= v1.0.4 is available
RUN pip install -U git+git://github.com/zooniverse/panoptes-python-client.git
RUN pip install -U awscli


ADD ./ /tprn
