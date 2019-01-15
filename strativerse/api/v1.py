
import json

from django import http
from django.core.exceptions import ObjectDoesNotExist

from strativerse.viewlist import ViewList, ViewField
from strativerse.models import Feature, Parameter, Person, Publication, Record
from strativerse.views import get_model_detail_url


class ErrorResponse(http.HttpResponse):
    def __init__(self, status_code, message, error_info=None):
        obj = {'error': message}
        if error_info is not None:
            obj['error_info'] = error_info

        super().__init__(json.dumps(obj))
        self.status_code = status_code


class StrativerseAPI:

    def detail_view(self, request, model_name, pk):
        raise NotImplementedError()

    def list_view(self, request, model_name):
        raise NotImplementedError()

    def related_view(self, request, model_name, pk, related_model_name):
        raise NotImplementedError()


class StratiViewList(ViewList):
    type = ViewField(lambda item: item._meta.model_name)
    id = ViewField()
    summary = ViewField('self')
    url = ViewField(lambda item: get_model_detail_url(item._meta.model_name, item.pk))
    created = ViewField(sortable=True)
    modified = ViewField(sortable=True)

    def __init__(self, request):
        super().__init__(data=request.GET)
        self.request = request

    def get_paginate_by(self):
        return 1000

    def get_related_viewlist_class(self, model_name):
        raise NotImplementedError()


class FeatureViewList(StratiViewList):
    name = ViewField(searchable=True, sortable=True)
    model = Feature


class PersonViewList(StratiViewList):
    given_names = ViewField(searchable=True)
    last_name = ViewField(searchable=True, sortable=True)
    model = Person


class ParameterViewList(StratiViewList):
    name = ViewField(searchable=True)
    slug = ViewField(searchable=True)
    description = ViewField(searchable=True)
    model = Parameter


class PublicationViewList(StratiViewList):
    slug = ViewField(search_key='authorships__person__last_name', sortable=True)
    year = ViewField(searchable=True, sortable=True)
    title = ViewField(searchable=True)
    abstract = ViewField()
    DOI = ViewField(searchable=True)
    URL = ViewField()
    model = Publication


class RecordViewList(StratiViewList):
    model = Record
    feature_id = ViewField(search_key='feature__name')


class StrativerseAPIv1(StrativerseAPI):

    def get_view_list(self, request, model_name):
        if model_name == 'Feature':
            viewlist = FeatureViewList
        elif model_name == 'Parameter':
            viewlist = ParameterViewList
        elif model_name == 'Person':
            viewlist = PersonViewList
        elif model_name == 'Publication':
            viewlist = PublicationViewList
        elif model_name == 'Record':
            viewlist = RecordViewList
        else:
            return None

        return viewlist(request)

    def detail_view(self, request, model_name, pk):
        viewlist = self.get_view_list(request, model_name)
        if viewlist is None:
            return ErrorResponse(404, f'No such type: "{model_name}"')
        try:
            obj = viewlist.model.objects.get(pk=pk)
            dct = viewlist.row_json(obj)
            return http.HttpResponse(json.dumps(dct))
        except ObjectDoesNotExist:
            return ErrorResponse(404, f'No {model_name} with id {pk}')

    def list_view(self, request, model_name):
        viewlist = self.get_view_list(request, model_name)
        if viewlist is None:
            return ErrorResponse(404, f'No such type: "{model_name}"')
        return http.HttpResponse(json.dumps(viewlist.as_json()))

    def related_view(self, request, model_name, pk, related_model_name):
        viewlist = self.get_view_list(request, model_name)
        if viewlist is None:
            return ErrorResponse(404, f'No such type: "{model_name}"')

        related_viewlist_class = viewlist.get_related_viewlist_class(related_model_name)
        if related_viewlist_class is None:
            return ErrorResponse(404, f'No {related_model_name} objects are related to {model_name} objects')

        try:
            obj = viewlist.model.objects.get(pk=pk)
            related_viewlist = related_viewlist_class(request, obj)
            return http.HttpResponse(json.dumps(related_viewlist.as_json()))
        except ObjectDoesNotExist:
            return ErrorResponse(404, f'No {model_name} with id {pk}')


api = StrativerseAPIv1()
