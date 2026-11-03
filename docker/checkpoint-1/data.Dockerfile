FROM python:3.12-slim

RUN pip install --no-cache-dir pyarrow==20.0.0 xxhash==3.5.0

WORKDIR /work
COPY prepare_sample.py reference.py download_sources.py /work/
