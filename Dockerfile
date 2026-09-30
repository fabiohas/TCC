FROM apache/airflow:2.9.1-python3.11

USER root
WORKDIR /opt/airflow

RUN apt-get update && \
    apt-get install -y --no-install-recommends chromium chromium-driver && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /requirements.txt

USER airflow
RUN pip install --no-cache-dir -r /requirements.txt

COPY . /opt/airflow

ENV PYTHONPATH=/opt/airflow
