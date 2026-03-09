from datetime import date
from django.db.utils import OperationalError, ProgrammingError

from .models import Customer, SiteVisit


class SiteVisitTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._track_visit(request)
        return self.get_response(request)

    def _track_visit(self, request):
        if request.method != 'GET':
            return

        path = request.path or ''
        if path.startswith('/admin/') or path.startswith('/static/') or path.startswith('/media/'):
            return

        session_key = request.session.session_key
        if not session_key:
            request.session.save()
            session_key = request.session.session_key

        if not session_key:
            return

        customer = None
        customer_id = request.session.get('customer_id')
        if customer_id:
            customer = Customer.objects.filter(id=customer_id).first()

        try:
            site_visit, created = SiteVisit.objects.get_or_create(
                visit_date=date.today(),
                session_key=session_key,
                defaults={
                    'customer': customer,
                },
            )

            if not created and customer and not site_visit.customer_id:
                site_visit.customer = customer
                site_visit.save(update_fields=['customer'])
        except (OperationalError, ProgrammingError):
            return
