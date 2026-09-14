from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('turmas/', include ('turmas.urls')),
    path('', include('core.urls')),
]
