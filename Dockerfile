FROM ubuntu

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        wget \
        ca-certificates \
        && rm -rf /var/lib/apt/lists/*
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
RUN bash Miniconda3-latest-Linux-x86_64.sh -b -f -p /anaconda

RUN ln -s /anaconda/etc/profile.d/conda.sh /etc/profile.d/conda.sh
RUN echo ". /anaconda/etc/profile.d/conda.sh" >> ~/.bashrc

WORKDIR /app
COPY ./environment.yml /app/
COPY ./manage.py /apps/
COPY ./package.json /apps/
COPY ./benchmarks /apps/
COPY ./static /apps/
COPY ./web /apps/
RUN /anaconda/bin/conda env create -f environment.yml
RUN echo "conda activate brain-score.web" >> ~/.bashrc

EXPOSE 80

ENTRYPOINT /bin/bash
CMD exec python manage.py runserver
