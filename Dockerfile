FROM python:latest

# Set the working directory in the container
WORKDIR /usr/src/app

#Set the environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

#Copy the requirements file into the container at /usr/src/app
COPY requirements.txt /usr/src/app/requirements.txt

# Install the dependencies
RUN pip install --no-cache-dir -r /usr/src/app/requirements.txt

COPY entrypoint.sh /usr/src/app/entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh

# Copy the current directory contents into the container at /usr/src/app
COPY . /usr/src/app

# Expose the port the app runs on
EXPOSE 8000
RUN ls -al /usr/src/app
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]

ENV DEFAULT_CMD="python manage.py runserver 0.0.0.0:8000"

ARG SERVICE_TYPE

ENV COMMAND=$SERVICE_TYPE

CMD /bin/sh -c "if [ '$COMMAND' = 'celery' ]; then celery --app=clinical_analytics worker -l INFO -Q tasks; else $DEFAULT_CMD; fi"


