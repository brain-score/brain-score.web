FROM continuumio/miniconda3
COPY . /app
WORKDIR /app
RUN conda env create -f environment.yml
RUN echo "source activate brain-score.web" > ~/.bashrc

EXPOSE 80

CMD ["/bin/bash", "python", "manage.py", "runserver", "0.0.0.0:80"]


