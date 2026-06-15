FROM continuumio/miniconda3:24.7.1-0

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY environment.yml /app/
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

RUN . ~/.bashrc && npm ci --no-optional
RUN . ~/.bashrc && npm install -g sass@1.69.5

EXPOSE 80

RUN . ~/.bashrc && python manage.py collectstatic --noinput

CMD . ~/.bashrc && python manage.py runserver --insecure 0.0.0.0:80
