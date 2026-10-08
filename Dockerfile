FROM continuumio/miniconda3:24.7.1-0

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY environment.yml /app/
COPY requirements-metadata.txt /app/
COPY manage.py /app/
COPY package.json /app/
COPY package-lock.json /app/
COPY news.yaml /app/
COPY benchmarks /app/benchmarks
COPY static /app/static
COPY web /app/web
COPY blog_posts /app/blog_posts
COPY tutorial_content /app/tutorial_content

RUN /opt/conda/bin/conda env create -f environment.yml
RUN echo "conda activate brain-score.web" >> ~/.bashrc

SHELL ["/bin/bash", "-c"]

# Keep the default aligned with infrastructure CI and METADATA_CORE_REF consumers.
ARG METADATA_CORE_REF="b72a9652f2121d9fb5734dd4418823086d4e95ea"
RUN [[ "$METADATA_CORE_REF" =~ ^[0-9a-f]{40}$ ]] || { echo 'METADATA_CORE_REF must be a full core commit SHA'; exit 1; }; \
    export METADATA_CORE_REF; \
    /opt/conda/bin/conda run -n brain-score.web python -m pip install -r requirements-metadata.txt && \
    /opt/conda/bin/conda run -n brain-score.web python -c "import brainscore_core.metadata" && \
    /opt/conda/bin/conda run -n brain-score.web python -m pip check

RUN . ~/.bashrc && npm ci --no-optional
RUN . ~/.bashrc && npm install -g sass@1.69.5

EXPOSE 80

RUN . ~/.bashrc && python manage.py collectstatic --noinput
RUN . ~/.bashrc && python manage.py compress --force

CMD . ~/.bashrc && gunicorn web.wsgi:application --bind 0.0.0.0:80 --workers 4 --threads 4 --worker-class gthread --timeout 60 --max-requests 1000 --max-requests-jitter 100 --access-logfile - --error-logfile -
