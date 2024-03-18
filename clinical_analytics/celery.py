import os
from celery import Celery
from kombu import Queue, Exchange
import time

# from clinical_analytics.data_upload.models import FileUploadData

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clinical_analytics.settings')
app = Celery("clinical_analytics")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.task_queues = [
    Queue('tasks', Exchange('tasks'), routing_key='tasks',
          queue_arguments={'x-max-priority': 10}),
]

app.conf.task_acks_late = True
app.conf.task_default_priority = 5
app.conf.worker_prefetch_multiplier = 1
app.conf.worker_concurrency = 1
app.autodiscover_tasks()





