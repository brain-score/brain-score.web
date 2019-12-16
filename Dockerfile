FROM continuumio/miniconda3

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY environment.yml /app/
COPY manage.py /app/
COPY package.json /app/
COPY benchmarks /app/benchmarks
COPY static /app/static
COPY web /app/web

RUN /opt/conda/bin/conda env create -f environment.yml
RUN echo "conda activate brain-score.web" >> ~/.bashrc

SHELL ["/bin/bash", "-c"]

RUN . ~/.bashrc && npm install --no-optional

EXPOSE 80

CMD . ~/.bashrc && python manage.py runserver 0.0.0.0:80