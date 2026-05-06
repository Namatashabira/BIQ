from rest_framework import serializers
from .models import Student, Stream, Guardian, StudentHistory, StudentMark, GeneratedReport
import os

try:
    import cloudinary
    import cloudinary.uploader
    _cloudinary_available = True
except ImportError:
    _cloudinary_available = False


class StreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stream
        fields = '__all__'


class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = '__all__'


class StudentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentHistory
        fields = '__all__'


class StudentMarkSerializer(serializers.ModelSerializer):
    total = serializers.ReadOnlyField()
    grade = serializers.ReadOnlyField()
    student_name = serializers.SerializerMethodField()
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)

    class Meta:
        model = StudentMark
        fields = '__all__'

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class GeneratedReportSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedReport
        fields = '__all__'

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class StudentSerializer(serializers.ModelSerializer):
    guardians = GuardianSerializer(many=True, read_only=True)
    history = StudentHistorySerializer(many=True, read_only=True)
    stream_name = serializers.CharField(source='stream.name', read_only=True)
    # Read-only: returns resolved URL
    photo = serializers.SerializerMethodField()
    # Write-only: accepts uploaded file
    photo_upload = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Student
        fields = '__all__'

    def get_photo(self, obj):
        if not obj.photo:
            return None
        try:
            url = obj.photo.url
            if url and (url.startswith('http://') or url.startswith('https://')):
                return url
            # Relative URL — make absolute
            request = self.context.get('request')
            if request:
                return value if value else None
        except Exception:
            return None

    def _save_photo(self, instance, photo_file):
        """Upload photo to Cloudinary or local storage and save on instance."""
        if _cloudinary_available:
            try:
                result = cloudinary.uploader.upload(
                    photo_file,
                    folder='student_photos',
                    public_id=f"student_{instance.id}",
                    overwrite=True,
                    resource_type='image',
                )
                # Store the Cloudinary public_id so CloudinaryField works correctly
                instance.photo = result.get('public_id') or result.get('secure_url')
                instance.save(update_fields=['photo'])
                return
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Cloudinary upload failed: {e}")
                if os.getenv('DJANGO_ENV') == 'production':
                    raise RuntimeError("Failed to upload photo to Cloudinary")
        else:
            if os.getenv('DJANGO_ENV') == 'production':
                raise RuntimeError("Cloudinary is not available in production")

        # Local storage fallback (only for development)
        instance.photo = photo_file
        instance.save(update_fields=['photo'])

    def create(self, validated_data):
        photo_file = validated_data.pop('photo_upload', None)
        student = super().create(validated_data)
        if photo_file:
            self._save_photo(student, photo_file)
        return student

    def update(self, instance, validated_data):
        photo_file = validated_data.pop('photo_upload', None)
        student = super().update(instance, validated_data)
        if photo_file:
            self._save_photo(student, photo_file)
        return student

    def validate_admission_number(self, value):
        return value if value and value.strip() else None

    def validate_stream(self, value):
        return value if value else None
