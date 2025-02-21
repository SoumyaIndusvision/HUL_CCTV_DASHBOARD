from django.apps import AppConfig


class MultiCamStreamConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'multi_cam_stream'

    def ready(self):
        """Ensure cleanup.py runs when Django starts."""
        from multi_cam_stream import cleanup
