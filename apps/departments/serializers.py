import os
import uuid
from django.core.files.storage import default_storage
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
    photo = serializers.FileField(required=False, write_only=True, allow_null=True)

    class Meta:
        model = Doctor
        fields = [
            'id', 'name', 'slug', 'department', 'department_name',
            'position', 'qualification', 'bio', 'photo_url', 'photo', 'phone',
            'email', 'twitter', 'facebook', 'google_plus', 'instagram',
            'is_active', 'created_at'
        ]
        extra_kwargs = {
            'slug': {'required': False, 'allow_blank': True},
            'photo_url': {'required': False, 'allow_blank': True, 'allow_null': True}
        }

    def validate_photo(self, value):
        if value:
            # Maximum 5 MB (5 * 1024 * 1024 bytes)
            max_size = 5 * 1024 * 1024
            if value.size > max_size:
                raise serializers.ValidationError("Doctor profile photo size cannot exceed 5 MB.")

            allowed_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
            ext = os.path.splitext(value.name)[1].lower()
            if ext not in allowed_extensions:
                raise serializers.ValidationError(
                    f"Unsupported image format '{ext}'. Allowed formats: JPG, JPEG, PNG, WebP."
                )

            # Validate binary magic bytes for image integrity without hard dependency on PIL
            try:
                pos = value.tell() if hasattr(value, 'tell') else 0
                if hasattr(value, 'seek'):
                    value.seek(0)
                header = value.read(16)
                if hasattr(value, 'seek'):
                    value.seek(pos)

                is_jpeg = header.startswith(b'\xff\xd8\xff')
                is_png = header.startswith(b'\x89PNG\r\n\x1a\n')
                is_webp = header.startswith(b'RIFF') and b'WEBP' in header[:16]

                if not (is_jpeg or is_png or is_webp):
                    raise serializers.ValidationError(
                        "Uploaded file is not a valid JPEG, PNG, or WebP image."
                    )
            except serializers.ValidationError:
                raise
            except Exception as e:
                raise serializers.ValidationError("Could not verify image integrity.")
        return value

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        photo_url = ret.get('photo_url')
        request = self.context.get('request')
        if photo_url and request and photo_url.startswith('/media/'):
            ret['photo_url'] = request.build_absolute_uri(photo_url)
        return ret

    def create(self, validated_data):
        photo_file = validated_data.pop('photo', None)
        if photo_file:
            ext = os.path.splitext(photo_file.name)[1].lower() or '.jpg'
            filename = f"doctors/doc_{uuid.uuid4().hex[:12]}{ext}"
            saved_path = default_storage.save(filename, photo_file)
            validated_data['photo_url'] = f"/media/{saved_path}"
        return super().create(validated_data)

    def update(self, instance, validated_data):
        photo_file = validated_data.pop('photo', None)
        if photo_file:
            ext = os.path.splitext(photo_file.name)[1].lower() or '.jpg'
            filename = f"doctors/doc_{uuid.uuid4().hex[:12]}{ext}"
            saved_path = default_storage.save(filename, photo_file)
            validated_data['photo_url'] = f"/media/{saved_path}"
        return super().update(instance, validated_data)

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
