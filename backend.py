import os, sys, json, django
from django.conf import settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not settings.configured:
    settings.configure(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'praxis-railway-secret-xyz-2026'),
        DEBUG=False,
        ALLOWED_HOSTS=['*'],
        INSTALLED_APPS=['django.contrib.contenttypes', 'django.contrib.auth', 'corsheaders'],
        MIDDLEWARE=['corsheaders.middleware.CorsMiddleware', 'django.middleware.common.CommonMiddleware'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.path.join(BASE_DIR, 'db.sqlite3')}},
        CORS_ALLOW_ALL_ORIGINS=True,
        ROOT_URLCONF=__name__,
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        USE_TZ=True,
        TIME_ZONE='Europe/Paris',
    )

django.setup()

from django.db import models

class AccessRequest(models.Model):
    first_name   = models.CharField(max_length=100)
    last_name    = models.CharField(max_length=100, blank=True)
    email        = models.EmailField()
    organisation = models.CharField(max_length=200, blank=True)
    profile      = models.CharField(max_length=50, blank=True)
    message      = models.TextField(blank=True)
    status       = models.CharField(max_length=20, default='pending')
    created_at   = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'auth'

class SimulationLog(models.Model):
    instability=models.IntegerField(default=0); conflict=models.IntegerField(default=0)
    alliances=models.IntegerField(default=0); dependency=models.IntegerField(default=0)
    disruption=models.IntegerField(default=0); budget=models.IntegerField(default=0)
    sanctions=models.IntegerField(default=0); global_risk=models.IntegerField(default=0)
    supply_score=models.IntegerField(default=0); eco_score=models.IntegerField(default=0)
    scenario=models.CharField(max_length=100, blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'auth'

# Run migrations on startup
from django.db import connection
with connection.schema_editor() as schema:
    try: schema.create_model(AccessRequest)
    except: pass
    try: schema.create_model(SimulationLog)
    except: pass

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta

def cors(response):
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

def health(request):
    return cors(JsonResponse({'status': 'ok', 'service': 'PRAXIS API', 'version': '1.0'}))

@csrf_exempt
def access_request_view(request):
    if request.method == 'OPTIONS':
        return cors(JsonResponse({}))
    if request.method != 'POST':
        return cors(JsonResponse({'error': 'Method not allowed'}, status=405))
    try:
        data = json.loads(request.body)
        first_name = data.get('first_name', '').strip()
        email = data.get('email', '').strip().lower()
        if not first_name or len(first_name) < 2:
            return cors(JsonResponse({'success': False, 'errors': {'first_name': 'First name too short'}}, status=400))
        if not email or '@' not in email:
            return cors(JsonResponse({'success': False, 'errors': {'email': 'Invalid email'}}, status=400))
        obj = AccessRequest.objects.create(
            first_name=first_name, last_name=data.get('last_name','').strip(),
            email=email, organisation=data.get('organisation','').strip(),
            profile=data.get('profile','').strip(), message=data.get('message','').strip()
        )
        return cors(JsonResponse({'success': True, 'message': 'Request received. We will contact you within 48 hours.', 'id': obj.pk}, status=201))
    except Exception as e:
        return cors(JsonResponse({'success': False, 'error': str(e)}, status=500))

@csrf_exempt
def log_simulation_view(request):
    if request.method == 'OPTIONS':
        return cors(JsonResponse({}))
    if request.method != 'POST':
        return cors(JsonResponse({'error': 'Method not allowed'}, status=405))
    try:
        data = json.loads(request.body)
        SimulationLog.objects.create(
            instability=int(data.get('instability',0)), conflict=int(data.get('conflict',0)),
            alliances=int(data.get('alliances',0)), dependency=int(data.get('dependency',0)),
            disruption=int(data.get('disruption',0)), budget=int(data.get('budget',0)),
            sanctions=int(data.get('sanctions',0)), global_risk=int(data.get('global_risk',0)),
            supply_score=int(data.get('supply_score',0)), eco_score=int(data.get('eco_score',0)),
            scenario=data.get('scenario','')
        )
        return cors(JsonResponse({'success': True}, status=201))
    except Exception as e:
        return cors(JsonResponse({'success': False, 'error': str(e)}, status=500))

def stats_view(request):
    s = SimulationLog.objects.aggregate(avg_risk=Avg('global_risk'), avg_supply=Avg('supply_score'), avg_eco=Avg('eco_score'), total=Count('id'))
    top = SimulationLog.objects.exclude(scenario='').values('scenario').annotate(c=Count('scenario')).order_by('-c').first()
    return cors(JsonResponse({
        'access_requests': AccessRequest.objects.count(),
        'total_simulations': s['total'] or 0,
        'recent_simulations_7d': SimulationLog.objects.filter(created_at__gte=timezone.now()-timedelta(days=7)).count(),
        'avg_global_risk': round(s['avg_risk'] or 0, 1),
        'avg_supply_vulnerability': round(s['avg_supply'] or 0, 1),
        'avg_economic_impact': round(s['avg_eco'] or 0, 1),
        'top_scenario': top['scenario'] if top else 'N/A',
    }))

from django.urls import path
urlpatterns = [
    path('health/', health),
    path('api/access-request/', access_request_view),
    path('api/log-simulation/', log_simulation_view),
    path('api/stats/', stats_view),
]

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
