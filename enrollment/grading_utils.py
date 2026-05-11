"""
Grading utilities for competence-based curriculum (CBC) report generation.
Supports dynamic grading systems per tenant and auto-generated teacher comments.
"""

from decimal import Decimal
from django.db.models import Q
from .models import Assessment, GradingSystem, Competency


def get_default_grading_system():
    """
    Returns default grading system boundaries and remarks.
    Used when tenant grading system hasn't been configured.
    """
    return {
        'grade_boundaries': {
            'A': 80,
            'B': 70,
            'C': 60,
            'D': 50,
            'E': 40,
            'F': 0
        },
        'remarks': {
            'A': 'Exceptional',
            'B': 'Outstanding',
            'C': 'Satisfactory',
            'D': 'Basic',
            'E': 'Elementary',
            'F': 'Fail'
        }
    }


def get_grade_and_remark(score, tenant=None):
    """
    Determine grade and remark based on score.
    Uses tenant-specific grading system or defaults if not configured.
    
    Args:
        score (float): Score out of 100
        tenant (Tenant): Tenant/School instance for custom grading
    
    Returns:
        dict: {'grade': 'A', 'remark': 'Exceptional', 'score': 85.5}
    """
    try:
        if tenant:
            grading_system = GradingSystem.objects.get(tenant=tenant)
            boundaries = grading_system.grade_boundaries
            remarks = grading_system.remarks
        else:
            default = get_default_grading_system()
            boundaries = default['grade_boundaries']
            remarks = default['remarks']
    except GradingSystem.DoesNotExist:
        default = get_default_grading_system()
        boundaries = default['grade_boundaries']
        remarks = default['remarks']
    
    # Sort boundaries in descending order to check from highest to lowest
    sorted_boundaries = sorted(boundaries.items(), key=lambda x: x[1], reverse=True)
    
    for grade, threshold in sorted_boundaries:
        if score >= threshold:
            return {
                'grade': grade,
                'remark': remarks.get(grade, 'N/A'),
                'score': round(score, 2)
            }
    
    # If score is below all thresholds, assign lowest grade
    lowest_grade = min(boundaries.items(), key=lambda x: x[1])[0]
    return {
        'grade': lowest_grade,
        'remark': remarks.get(lowest_grade, 'N/A'),
        'score': round(score, 2)
    }


def calculate_subject_average(student, subject, term, academic_year):
    """
    Calculate average score for a subject across all assessments in a term.
    
    Args:
        student (Student): Student instance
        subject (Subject): Subject instance
        term (str): Term identifier
        academic_year (str): Academic year
    
    Returns:
        float: Average score (0-100)
    """
    assessments = Assessment.objects.filter(
        student=student,
        subject=subject,
        term=term,
        academic_year=academic_year
    )
    
    if not assessments.exists():
        return 0
    
    # Calculate weighted average based on assessment type
    # Exams count more than CA
    weight_map = {
        'exam': 0.6,
        'ca': 0.3,
        'practical': 0.1,
        'project': 0.15,
        'participation': 0.05
    }
    
    total_score = 0
    total_weight = 0
    
    for assessment in assessments:
        weight = weight_map.get(assessment.assessment_type, 0.1)
        percentage = (assessment.score / assessment.out_of * 100) if assessment.out_of > 0 else 0
        total_score += percentage * weight
        total_weight += weight
    
    return round(total_score / total_weight, 2) if total_weight > 0 else 0


def calculate_competency_average(student, competency, term, academic_year):
    """
    Calculate average score for a specific competency.
    
    Args:
        student (Student): Student instance
        competency (Competency): Competency instance
        term (str): Term identifier
        academic_year (str): Academic year
    
    Returns:
        float: Average score for competency
    """
    assessments = Assessment.objects.filter(
        student=student,
        competency=competency,
        term=term,
        academic_year=academic_year
    )
    
    if not assessments.exists():
        return 0
    
    total_score = 0
    total_out_of = 0
    
    for assessment in assessments:
        total_score += assessment.score
        total_out_of += assessment.out_of
    
    return round((total_score / total_out_of * 100), 2) if total_out_of > 0 else 0


def calculate_overall_average(student, term, academic_year, tenant=None):
    """
    Calculate overall average across all subjects in a term.
    
    Args:
        student (Student): Student instance
        term (str): Term identifier
        academic_year (str): Academic year
        tenant (Tenant): Tenant for multi-tenant support
    
    Returns:
        float: Overall average score
    """
    from .models import Subject
    
    # Get all subjects for this student's class
    enrollments = student.enrollments.filter(
        term_or_semester=term,
        academic_year=academic_year
    )
    
    if not enrollments.exists():
        return 0
    
    # Get subjects for the student's class/grade
    student_class = enrollments.first().grade_or_class
    subjects = Subject.objects.filter(
        tenant=tenant,
        class_or_grade=student_class,
        is_active=True
    )
    
    if not subjects.exists():
        return 0
    
    subject_averages = []
    for subject in subjects:
        avg = calculate_subject_average(student, subject, term, academic_year)
        if avg > 0:
            subject_averages.append(avg)
    
    if not subject_averages:
        return 0
    
    overall = sum(subject_averages) / len(subject_averages)
    return round(overall, 2)


def generate_teacher_comment(student, overall_score, subject_scores, tenant=None):
    """
    Generate auto-comment based on performance metrics.
    Can be customized per tenant.
    
    Args:
        student (Student): Student instance
        overall_score (float): Overall average score
        subject_scores (list): List of subject scores
        tenant (Tenant): Tenant for custom comments
    
    Returns:
        str: Generated teacher comment
    """
    try:
        grading_system = GradingSystem.objects.get(tenant=tenant) if tenant else None
    except GradingSystem.DoesNotExist:
        grading_system = None
    
    excellent_threshold = grading_system.excellent_threshold if grading_system else 80
    good_threshold = grading_system.good_threshold if grading_system else 70
    average_threshold = grading_system.average_threshold if grading_system else 60
    weak_threshold = grading_system.weak_threshold if grading_system else 50
    
    student_name = f"{student.first_name} {student.last_name}"
    
    # Determine performance level
    if overall_score >= excellent_threshold:
        comment = f"{student_name} has demonstrated exceptional performance across most subjects. "
        comment += "Keep up the excellent work and maintain this high standard."
    elif overall_score >= good_threshold:
        comment = f"{student_name} has shown outstanding performance this term. "
        comment += "Continue to build on this momentum and aim for excellence."
    elif overall_score >= average_threshold:
        comment = f"{student_name} has performed satisfactorily this term. "
        comment += "With more focus and effort, further improvement is achievable."
    elif overall_score >= weak_threshold:
        comment = f"{student_name} has shown basic competency this term. "
        comment += "Immediate attention is needed to improve performance in weaker areas."
    else:
        comment = f"{student_name} requires significant support and intervention. "
        comment += "Please discuss with parents/guardians regarding remedial measures."
    
    # Analyze subject consistency
    if subject_scores:
        strong_subjects = sum(1 for s in subject_scores if s['score'] >= excellent_threshold)
        weak_subjects = sum(1 for s in subject_scores if s['score'] < average_threshold)
        
        if strong_subjects > 0 and weak_subjects == 0:
            comment += " All subjects show consistent high performance."
        elif weak_subjects > weak_subjects / 2:
            comment += f" Particular attention is needed in {weak_subjects} subject(s)."
    
    return comment


def get_competency_grades_for_subject(student, subject, term, academic_year, tenant=None):
    """
    Get grades for all competencies within a subject.
    
    Args:
        student (Student): Student instance
        subject (Subject): Subject instance
        term (str): Term identifier
        academic_year (str): Academic year
        tenant (Tenant): Tenant for grading system
    
    Returns:
        list: List of competency grades
    """
    competencies = subject.competencies.filter(is_active=True)
    
    competency_grades = []
    for competency in competencies:
        avg_score = calculate_competency_average(
            student, competency, term, academic_year
        )
        
        if avg_score > 0:
            grade_info = get_grade_and_remark(avg_score, tenant)
            competency_grades.append({
                'competency_code': competency.code,
                'competency_name': competency.name,
                'score': avg_score,
                'grade': grade_info['grade'],
                'remark': grade_info['remark'],
                'weighting': competency.weighting
            })
    
    return competency_grades


def generate_report_data(student, term, academic_year, tenant=None):
    """
    Generate complete report data for a student in a term.
    This is the main function called by API views.
    
    Args:
        student (Student): Student instance
        term (str): Term identifier
        academic_year (str): Academic year
        tenant (Tenant): Tenant for queries and grading system
    
    Returns:
        dict: Complete report data
    """
    from .models import Subject
    
    # Get student's class/grade
    enrollment = student.enrollments.filter(
        term_or_semester=term,
        academic_year=academic_year
    ).first()
    
    if not enrollment:
        return None
    
    # Get all subjects for this class
    subjects = Subject.objects.filter(
        tenant=tenant,
        class_or_grade=enrollment.grade_or_class,
        is_active=True
    )
    
    # Calculate subject performance
    subject_performance = []
    subject_scores = []
    
    for subject in subjects:
        subject_avg = calculate_subject_average(
            student, subject, term, academic_year
        )
        
        if subject_avg > 0 or Assessment.objects.filter(
            student=student,
            subject=subject,
            term=term,
            academic_year=academic_year
        ).exists():
            grade_info = get_grade_and_remark(subject_avg, tenant)
            
            # Get competency breakdown
            competency_grades = get_competency_grades_for_subject(
                student, subject, term, academic_year, tenant
            )
            
            subject_data = {
                'subject_code': subject.code,
                'subject_name': subject.name,
                'score': subject_avg,
                'grade': grade_info['grade'],
                'remark': grade_info['remark'],
                'competencies': competency_grades
            }
            
            subject_performance.append(subject_data)
            subject_scores.append({
                'subject': subject.name,
                'score': subject_avg,
                'grade': grade_info['grade']
            })
    
    # Calculate overall performance
    overall_score = calculate_overall_average(student, term, academic_year, tenant)
    overall_grade_info = get_grade_and_remark(overall_score, tenant)
    
    # Generate teacher comment (rule-based fallback)
    teacher_comment = generate_teacher_comment(
        student, overall_score, subject_scores, tenant
    )

    # Generate AI comment and use it if available
    try:
        from ai_comments.services import generate_ai_comment
        subject_perf_dict = {s['subject_name']: {'score': s['score'], 'grade': s['grade']} for s in subject_performance}
        ai_comment, used_ai = generate_ai_comment(
            student_name=f"{student.first_name} {student.last_name}",
            overall_score=overall_score,
            subject_performance=subject_perf_dict,
            term=term,
            academic_year=academic_year
        )
        if used_ai:
            teacher_comment = ai_comment
    except Exception:
        pass  # keep rule-based comment on any error
    
    return {
        'student': {
            'id': str(student.id),
            'admission_number': student.admission_number,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'full_name': f"{student.first_name} {student.last_name}",
            'date_of_birth': student.date_of_birth,
            'gender': student.gender,
            'class_or_grade': enrollment.grade_or_class,
            'stream': enrollment.stream or 'N/A'
        },
        'subjects': subject_performance,
        'overall': {
            'score': overall_score,
            'grade': overall_grade_info['grade'],
            'remark': overall_grade_info['remark'],
            'teacher_comment': teacher_comment,
            'ai_comment': teacher_comment,
            'total_subjects': len(subject_performance)
        },
        'metadata': {
            'term': term,
            'academic_year': academic_year,
            'generated_at': str(__import__('django.utils.timezone', fromlist=['now']).now())
        }
    }
