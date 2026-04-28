from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Appointment
import logging

logger = logging.getLogger("core.reminders")

class Command(BaseCommand):
    help = "Send due appointment reminders (logs only)."

    def handle(self, *args, **options):
        now = timezone.now()
        due = Appointment.objects.filter(
            reminder_sent=False,
        )
        count = 0
        for appt in due:
            delta = appt.start_time - now
            minutes_before = appt.reminder_minutes_before or 30
            if delta.total_seconds() <= minutes_before * 60:
                # In real life: send email/SMS/notification here
                logger.info("Reminder: %s at %s", appt.title, appt.start_time)
                appt.reminder_sent = True
                appt.save(update_fields=["reminder_sent"])
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Sent {count} reminders"))
