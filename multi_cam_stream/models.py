from django.db import models

class Seracs(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "Seracs"

    def __str__(self):
        return self.name

class Section(models.Model):
    name = models.CharField(max_length=100)
    serac = models.ForeignKey(Seracs, related_name='sections', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.name} ({self.serac.name})"

class Camera(models.Model):
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField(default=554)
    username = models.CharField(max_length=50, blank=True, null=True)
    password = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    section = models.ForeignKey(Section, related_name='cameras', on_delete=models.SET_NULL, null=True)

    def get_rtsp_url(self):
        """Generates the RTSP URL for the camera"""
        if self.username and self.password:
            return f"rtsp://{self.username}:{self.password}@{self.ip_address}:{self.port}/cam/realmonitor?channel=1&subtype=0"
        return f"rtsp://{self.ip_address}:{self.port}/cam/realmonitor?channel=1&subtype=0"

    def __str__(self):
        return self.name
