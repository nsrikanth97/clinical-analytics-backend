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


COPY ./entrypoint.sh /usr/src/app/entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh

# Copy the current directory contents into the container at /usr/src/app
COPY . /usr/src/app

# Expose the port the app runs on
EXPOSE 8000
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
# Run the application
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

