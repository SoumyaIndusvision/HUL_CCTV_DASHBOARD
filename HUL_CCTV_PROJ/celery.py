# import os
# from celery import Celery

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "HUL_CCTV_PROJ.settings")

# celery_app = Celery("HUL_CCTV_PROJ")
# celery_app.config_from_object("django.conf:settings", namespace="CELERY")
# celery_app.autodiscover_tasks()