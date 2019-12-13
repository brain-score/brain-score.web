FROM ubuntu

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        wget \
        ca-certificates \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

SHELL ["/bin/bash", "-c"]

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
RUN bash Miniconda3-latest-Linux-x86_64.sh -b -f -p /opt/conda
RUN echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc

COPY ./environment.yml /app/
COPY ./manage.py /app/
COPY ./package.json /app/
COPY ./benchmarks /app/
COPY ./static /app/
COPY ./web /app/

RUN /opt/conda/bin/conda env create -f environment.yml
RUN echo "conda activate brain-score.web" >> ~/.bashrc

EXPOSE 80

#ENTRYPOINT python manage.py runserver
#CMD python manage.py runserver
#CMD conda info
#CMD cat ~/.bashrc
CMD /bin/bash
