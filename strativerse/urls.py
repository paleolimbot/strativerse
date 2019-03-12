
from django.conf.urls import url
from . import views
from .api.v1 import api

app_name = 'strativerse'
urlpatterns = [
    # the model redirect view
    url(r'^detail/(?P<model>[a-z0-9]+)/(?P<pk>[0-9]+)$', views.ModelDetailRedirectView.as_view(), name="detail"),
    # APIv1
    url(r'^api/v1/(?P<model_name>[a-z0-9]+)/(?P<pk>[0-9]+)$',
        api.detail_view,
        name='apiv1_detail'),
    url(r'^api/v1/(?P<model_name>[a-z0-9]+)$',
        api.list_view,
        name='apiv1_list'),
    url(r'^api/v1/(?P<model_name>[a-z0-9]+)/(?P<related_model_name>[a-z0-9])$',
        api.related_view,
        name='apiv1_related')
]
