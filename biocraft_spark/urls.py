"""
URL configuration for biocraft_spark project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from workbench.views import docker_ping, executor_ping, home, scheduler_ping

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("debug/ping-docker/", docker_ping, name="docker_ping"),
    path("debug/ping-docker", docker_ping),
    path("debug/ping-executor/", executor_ping, name="executor_ping"),
    path("debug/ping-executor", executor_ping),
    path("debug/ping-scheduler/", scheduler_ping, name="scheduler_ping"),
    path("debug/ping-scheduler", scheduler_ping),
]
