from django.contrib import admin
from django.urls import path, include 

urlpatterns = [
    path('admin/', admin.site.urls),

    path('chamada/', include('chamada.urls')),

    path('', include('core.urls')),
]
