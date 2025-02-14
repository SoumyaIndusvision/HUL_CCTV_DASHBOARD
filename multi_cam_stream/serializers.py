from rest_framework import serializers
from .models import Seracs, Section, Camera


class SeracSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seracs
        fields = '__all__'


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = '__all__' 

    
class CameraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Camera
        fields = '__all__'

