
from django.views.generic import RedirectView
from django.http import Http404
from django.urls import reverse_lazy

_model_detail_urls_patterns = {}


def register_model_detail_url(model, url_id):
    global _model_detail_urls_patterns
    if not isinstance(model, str):
        model = model.__name__.lower()

    previous = _model_detail_urls_patterns[model] if  model in _model_detail_urls_patterns else None
    if url_id is None:
        del _model_detail_urls_patterns[model]
    else:
        _model_detail_urls_patterns[model] = url_id
    return previous


class ModelDetailRedirectView(RedirectView):

    def get_redirect_url(self, model, pk):
        if model not in _model_detail_urls_patterns:
            raise Http404('Model not found: "{}"'.format(model))
        else:
            return reverse_lazy(_model_detail_urls_patterns[model], kwargs={'pk': pk})
