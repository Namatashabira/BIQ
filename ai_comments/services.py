import os
import requests


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"


def _rule_based_comment(student_name, overall_score, subject_performance):
    """Fallback rule-based comment when Gemini is unavailable."""
    if overall_score >= 80:
        opening = f"{student_name} has demonstrated exceptional academic performance this term."
        closing = "Keep up the outstanding work!"
    elif overall_score >= 70:
        opening = f"{student_name} has shown commendable effort and good academic progress this term."
        closing = "Continue working hard to reach even greater heights."
    elif overall_score >= 60:
        opening = f"{student_name} has performed satisfactorily this term."
        closing = "With more focus and dedication, better results are achievable."
    elif overall_score >= 50:
        opening = f"{student_name} has shown basic understanding of the curriculum this term."
        closing = "More effort and consistent study habits are strongly encouraged."
    else:
        opening = f"{student_name} needs significant improvement in academic performance."
        closing = "Regular attendance, extra study, and teacher support are highly recommended."

    subject_note = ""
    if subject_performance:
        sorted_subjects = sorted(
            subject_performance.items(),
            key=lambda x: x[1].get('score', 0) if isinstance(x[1], dict) else 0,
            reverse=True
        )
        best = sorted_subjects[0][0] if sorted_subjects else None
        worst = sorted_subjects[-1][0] if len(sorted_subjects) > 1 else None
        if best:
            subject_note += f" Particularly strong in {best}."
        if worst and worst != best:
            subject_note += f" Needs more attention in {worst}."

    return f"{opening}{subject_note} {closing}"


def generate_ai_comment(student_name, overall_score, subject_performance, term, academic_year):
    """
    Generate an AI comment using Google Gemini.
    Falls back to rule-based if Gemini is unavailable.
    """
    api_key = os.getenv('GEMINI_API_KEY')

    if api_key:
        try:
            subjects_summary = "\n".join([
                f"- {subj}: {data.get('score', 'N/A')}/100 (Grade: {data.get('grade', 'N/A')})"
                if isinstance(data, dict) else f"- {subj}: {data}"
                for subj, data in (subject_performance or {}).items()
            ])

            prompt = f"""You are a professional school teacher writing a report card comment.
Write a concise, encouraging, and constructive comment (2-3 sentences) for:

Student: {student_name}
Term: {term}, Academic Year: {academic_year}
Overall Score: {overall_score:.1f}%

Subject Performance:
{subjects_summary or 'No subject data available'}

Guidelines:
- Be specific about strengths and areas for improvement
- Use a warm, professional tone
- Do NOT use the student's full name more than once
- Keep it under 60 words
"""

            response = requests.post(
                GEMINI_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-goog-api-key": api_key,
                },
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=15
            )

            if response.status_code == 200:
                data = response.json()
                comment = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return comment, True

        except Exception:
            pass  # Fall through to rule-based

    return _rule_based_comment(student_name, overall_score, subject_performance or {}), False
