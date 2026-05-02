from rest_framework import serializers
from .models import Student, Stream, Guardian, StudentHistory, StudentMark, GeneratedReport


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

    class Meta:
        model = Student
        fields = '__all__'

    def validate_admission_number(self, value):
        return value if value and value.strip() else None

    def validate_stream(self, value):
        return value if value else None
