from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from students.models import Student, StudentMark
from .models import AIReportComment
from .serializers import AIReportCommentSerializer
from .services import generate_ai_comment


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_comment(request):
    """
    Generate an AI comment for a student's report card.
    Body: { student_id, term, academic_year }
    """
    student_id = request.data.get('student_id')
    term = request.data.get('term')
    academic_year = request.data.get('academic_year')

    if not all([student_id, term, academic_year]):
        return Response(
            {'error': 'student_id, term, and academic_year are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    student = get_object_or_404(Student, id=student_id)
    student_name = f"{student.first_name} {student.last_name}"

    # Build subject performance from StudentMark
    marks = StudentMark.objects.filter(
        student=student, term=term, academic_year=academic_year
    )
    overall_score = 0.0
    subject_performance = {}

    if marks.exists():
        for m in marks:
            total = (m.ca_score or 0) + (m.exam_score or 0)
            subject_performance[m.subject] = {'score': total, 'grade': m.grade}
        overall_score = round(
            sum(v['score'] for v in subject_performance.values()) / len(subject_performance), 2
        )

    comment_text, used_ai = generate_ai_comment(
        student_name, overall_score, subject_performance, term, academic_year
    )

    ai_comment, created = AIReportComment.objects.update_or_create(
        student=student,
        term=term,
        academic_year=academic_year,
        defaults={
            'comment': comment_text,
            'overall_score': overall_score,
            'generated_by_ai': used_ai,
        }
    )

    serializer = AIReportCommentSerializer(ai_comment)
    return Response(
        {**serializer.data, 'generated_by_ai': used_ai},
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_comment(request, student_id):
    term = request.query_params.get('term')
    academic_year = request.query_params.get('academic_year')

    filters = {'student_id': student_id}
    if term:
        filters['term'] = term
    if academic_year:
        filters['academic_year'] = academic_year

    comments = AIReportComment.objects.filter(**filters).order_by('-created_at')
    if not comments.exists():
        return Response({'error': 'No AI comment found'}, status=status.HTTP_404_NOT_FOUND)

    return Response(AIReportCommentSerializer(comments.first()).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_comment(request, pk):
    ai_comment = get_object_or_404(AIReportComment, pk=pk)
    new_comment = request.data.get('comment')
    if not new_comment:
        return Response({'error': 'comment field required'}, status=status.HTTP_400_BAD_REQUEST)
    ai_comment.comment = new_comment
    ai_comment.generated_by_ai = False
    ai_comment.save()
    return Response(AIReportCommentSerializer(ai_comment).data)
