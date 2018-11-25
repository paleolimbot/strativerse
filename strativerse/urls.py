
from django.conf.urls import url
from . import views

app_name = 'strativerse'
urlpatterns = [
    # the model redirect view
    url(r'^detail/(?P<model>[a-z0-9]+)/(?P<pk>[0-9]+)$', views.ModelDetailRedirectView.as_view(), name="detail"),
]
