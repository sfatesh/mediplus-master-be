from rest_framework import serializers
from django.utils.text import slugify
from .models import Department, Doctor


class DepartmentSerializer(serializers.ModelSerializer):
    doctors_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            'id', 'name', 'slug', 'icon', 'description',
            'image_url', 'is_active', 'created_at', 'doctors_count'
        ]
        extra_kwargs = {
            'slug': {'required': False, 'allow_blank': True}
        }

    def get_doctors_count(self, obj) -> int:
        return obj.doctors.filter(is_active=True).count()

    def validate(self, attrs):
        if not attrs.get('slug') and attrs.get('name'):
            base_slug = slugify(attrs['name'])
            slug = base_slug
            counter = 1
            qs = Department.objects.filter(slug=slug)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            while qs.exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
                qs = Department.objects.filter(slug=slug)
                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)
            attrs['slug'] = slug
        return attrs


class DoctorSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Doctor
        fields = [
            'id', 'name', 'slug', 'department', 'department_name',
            'position', 'qualification', 'bio', 'photo_url', 'phone',
            'email', 'twitter', 'facebook', 'google_plus', 'instagram',
            'is_active', 'created_at'
        ]
        extra_kwargs = {
            'slug': {'required': False, 'allow_blank': True}
        }

    def validate(self, attrs):
        if not attrs.get('slug') and attrs.get('name'):
            base_slug = slugify(attrs['name'])
            slug = base_slug
            counter = 1
            qs = Doctor.objects.filter(slug=slug)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            while qs.exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
                qs = Doctor.objects.filter(slug=slug)
                if self.instance:
                    qs = qs.exclude(pk=self.instance.pk)
            attrs['slug'] = slug
        return attrs
