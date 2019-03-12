
import json
import re

from django import forms
from django.db.models import F, Q
from django.core.exceptions import ImproperlyConfigured
from django.core.paginator import Paginator, Page, EmptyPage
from django.utils.functional import cached_property
from django.template.loader import get_template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.http.request import QueryDict
from django.urls import reverse_lazy


class ViewField(forms.CharField):
    key = None
    sort_key = None
    view_key = None
    search_key = None

    def __init__(self, key=None, sort_key=None, search_key=None,
                 searchable=None, sortable=None, visible=True, filters=None,
                 null_values=None, **kwargs):
        if key is not None:
            self.key = key
        if sort_key is not None:
            self.sort_key = sort_key

        if sortable is None and self.sort_key is not None:
            sortable = True

        if search_key is not None:
            self.search_key = search_key

        if searchable is None and self.search_key is not None:
            searchable = True

        super().__init__(**kwargs)
        self._searchable = searchable
        self._sortable = sortable
        if not visible:
            self.widget = forms.HiddenInput()
        self.visible = visible

        self.sort_direction = None
        self.viewlist = None
        self.name = None
        self.filters = filters if filters is not None else {}
        if null_values is None:
            null_values = {}
        self.null_values = {'html': '-', 'text': '', 'json': None}
        self.null_values.update(null_values)

    def is_sortable(self):
        return self._sortable is True

    def is_searchable(self):
        return self._searchable is True

    def get_bound_field(self, form, field_name):
        bf = super().get_bound_field(form, field_name)
        bf.sort_link = self.sort_link()
        bf.is_sortable = self.is_sortable()
        return bf

    def sort_link(self, base_url=''):
        if self.is_sortable():
            if self.sort_direction == 'asc':
                sort_value = '-' + self.name
            else:
                sort_value = self.name

            return base_url + '?' + self.viewlist.get_query_string(
                **{self.viewlist.order_var: sort_value, self.viewlist.page_var: None}
            )
        else:
            return base_url + '#'

    def sort_queryset(self, queryset, decreasing=False):
        key = self.sort_key if self.sort_key is not None else self.key
        if key is None:
            raise ImproperlyConfigured('There is no key in this ViewField')

        if decreasing:
            self.sort_direction = 'desc'
            return queryset.order_by('-' + key)
        else:
            self.sort_direction = 'asc'
            return queryset.order_by(key)

    def search_expression(self, query):
        key = self.search_key if self.search_key is not None else self.key
        if not isinstance(key, str):
            raise ImproperlyConfigured('ViewField must implement search_queryset() if self.search_key is not a string')
        if query:
            return Q(**{key + '__icontains': query})
        else:
            return None

    def prepare_queryset(self, queryset):
        if self.key is None:
            raise ImproperlyConfigured('There is no key in this ViewField')
        if isinstance(self.key, str) and '__' in self.key:
            return queryset.annotate(**{self.key: F(self.key)})
        else:
            return queryset

    def value_base(self, item, key, default=None):
        if key == 'self':
            return item
        elif isinstance(key, str):
            if hasattr(item, key):
                value = getattr(item, key)
            elif hasattr(item, '__contains__') and key in item:
                value = item[key]
            else:
                value = default

            if callable(value):
                value = value()

            return value

        elif callable(key):
            return self.key(item)
        else:
            raise ImproperlyConfigured('key is not a string or callable')

    def value_text(self, item, default=None):
        value = self.value_base(item, self.key, default)
        if 'text' in self.null_values and not value:
            value = self.null_values['text']
        if 'text' in self.filters:
            value = self.filters['text'](value)

        return value

    def value_html(self, item, default=None):
        value = self.value_base(item, self.key, default)
        if 'html' in self.null_values and not value:
            value = self.null_values['html']
        if 'html' in self.filters:
            value = self.filters['html'](value)

        return value

    def value_json(self, item, default=None):
        value = self.value_base(item, self.key, default)
        if 'json' in self.null_values and not value:
            value = self.null_values['json']
        if 'json' in self.filters:
            value = self.filters['json'](value)

        return value


class UrlPatternViewField(ViewField):

    def __init__(self, *args, url_pattern=None, url_kwargs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.url_pattern = url_pattern
        self.url_kwargs = url_kwargs

    def prepare_queryset(self, queryset):
        queryset = super().prepare_queryset(queryset)
        if self.url_kwargs:
            queryset = queryset.annotate(**{key: F(key) for key in self.url_kwargs.values()})
        return queryset

    def value_html(self, item, default=None):
        value = super().value_html(item, default)
        if value and self.url_pattern and self.url_kwargs:
            url_kwargs = {kword: self.value_base(item, key) for kword, key in self.url_kwargs.items()}
            url_kwargs = {k: v for k, v in url_kwargs.items() if v is not None}
            if url_kwargs:
                return format_html(
                    '<a href="{}">{}</a>',
                    reverse_lazy(self.url_pattern, kwargs=url_kwargs),
                    value
                )

        return value


class LinkViewField(ViewField):

    def __init__(self, *args, link_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.link_key = link_key

    def prepare_queryset(self, queryset):
        queryset = super().prepare_queryset(queryset)
        model_fields = [f.name for f in queryset.model._meta.fields]
        if self.link_key and self.link_key in model_fields:
            queryset = queryset.annotate(**{self.link_key: F(self.link_key)})
        return queryset

    def value_html(self, item, default=None):
        value = super().value_html(item, default)
        if value and self.link_key:
            link = self.value_base(item, self.link_key, default=None)
            if link is not None:
                return format_html(
                    '<a href="{}" target="_blank">{}</a>',
                    link,
                    value
                )

        return value


class ViewList(forms.Form):
    model = None
    search_form_class = None
    order_var = '_o'
    page_var = '_p'
    search_var = '_q'
    paginate_by = None
    template_name = 'viewlist/viewlist_table.html'

    class Media:
        css = {'all': ['viewlist/viewlist.css']}

    def __init__(self, data=None):
        if self.prefix is None and self.model is not None:
            self.prefix = self.model._meta.model_name

        super().__init__(prefix=self.prefix)

        self.data = data

        for name, field in self.fields.items():
            if not isinstance(field, ViewField):
                raise ImproperlyConfigured('field in a ViewList is not a ViewField')
            if field.key is None:
                field.key = name

            field.viewlist = self
            field.name = name

        if self.search_form_class is None:
            self.search_form = forms.Form(prefix=self.prefix, data=data)
            if self.is_searchable():
                self.search_form.fields[self.search_var] = forms.CharField(required=False, label='Search')
        else:
            self.search_form = self.search_form_class(prefix=self.prefix)

        self.search_form.fields[self.order_var] = forms.CharField(required=False, widget=forms.HiddenInput)

    def is_searchable(self):
        return any(field.is_searchable() for field in self.fields.values())

    def is_paginated(self):
        return isinstance(self.object_list, Page) and self.object_list.paginator.num_pages > 1

    def get_paginate_by(self):
        return self.paginate_by

    def form_action(self):
        return self.get_query_string()

    def get_query_string(self, **kwargs):
        query_dict = QueryDict(mutable=True)
        prefix = self.prefix + '-' if self.prefix else ''
        if self.data:
            query_dict.update(self.data)
        for key, value in kwargs.items():
            if value is None:
                if (prefix + key) in query_dict:
                    del query_dict[prefix + key]
            else:
                query_dict[prefix + key] = value

        return query_dict.urlencode()

    def object_name(self):
        if self.model is None:
            return 'object'
        else:
            return self.model._meta.verbose_name

    def object_name_plural(self):
        if self.model is None:
            return 'objects'
        else:
            return self.model._meta.verbose_name_plural

    def get_queryset(self):
        if self.model is None:
            raise ImproperlyConfigured('self.model is not defined for this ViewList')
        return self.model.objects.all()

    def filter_queryset(self, queryset):
        if self.search_form._errors is None:
            self.search_form.full_clean()

        if self.search_var not in self.search_form.fields or not self.search_form.is_valid:
            return queryset

        expression = None
        query = self.search_form.cleaned_data[self.search_var]
        for field in self.fields.values():
            if field.is_searchable():
                expr = field.search_expression(query)
                if expr is None:
                    continue
                if expression is None:
                    expression = expr
                else:
                    expression = expression | expr

        if expression is not None:
            return queryset.filter(expression).distinct()
        else:
            return queryset

    def sort_queryset(self, queryset):
        if self.search_form._errors is None:
            self.search_form.full_clean()

        if not self.search_form.is_valid:
            return queryset

        order_value = self.search_form.cleaned_data[self.order_var]
        order_field = re.sub(r'^-', '', order_value)
        decreasing = bool(re.search(r'^-', order_value))
        for name, field in self.fields.items():
            if name == order_field:
                if field.is_sortable():
                    queryset = field.sort_queryset(queryset, decreasing=decreasing)
                else:
                    # this doesn't show up as an error quite yet
                    self.search_form.add_error(None, forms.ValidationError('Cannot order by field "%s"' % order_field))
                break
        return queryset

    def finalize_queryset(self, queryset):
        for field in self.fields.values():
            queryset = field.prepare_queryset(queryset)
        return queryset

    def paginate(self, queryset):
        paginate_by = self.get_paginate_by()
        if paginate_by is not None:
            page_num = 1
            if self.data:
                try:
                    prefix = self.prefix + '-' if self.prefix else ''
                    page_num = max(1, int(self.data.get(prefix + self.page_var, 1)))
                except ValueError:
                    page_num = 1

            try:
                return Paginator(queryset, paginate_by).page(page_num)
            except EmptyPage:
                return queryset.none()
        else:
            return queryset

    def assemble_queryset(self):
        queryset = self.get_queryset()
        queryset = self.sort_queryset(queryset)
        queryset = self.filter_queryset(queryset)
        queryset = self.finalize_queryset(queryset)
        return self.paginate(queryset)

    @cached_property
    def object_list(self):
        return self.assemble_queryset()

    def get_context_data(self):
        # it is important that the object list is generated before this point
        ol = self.object_list
        return {'viewlist': self}

    def rowiter_text(self):
        for item in self.object_list:
            yield self.row_text(item)

    def rowiter_html(self):
        for item in self.object_list:
            yield self.row_html(item)

    def rowiter_json(self):
        for item in self.object_list:
            yield self.row_json(item)

    def row_text(self, item):
        return [field.value_text(item) for field in self.fields.values() if field.visible]

    def row_html(self, item):
        return [field.value_html(item) for field in self.fields.values() if field.visible]

    def row_json(self, item):
        return {field.name: field.value_json(item) for field in self.fields.values() if field.visible}

    def as_json(self):
        return json.dumps(list(self.rowiter_json()))

    def pagination_widget(self, null_html=''):

        page = self.object_list

        if not isinstance(page, Page):
            # straight queryset
            return mark_safe(null_html)

        paginator, page_num = page.paginator, page.number

        if paginator.num_pages <= 1:
            return ''

        ON_EACH_SIDE = 3
        ON_ENDS = 2

        # If there are 10 or fewer pages, display links to every page.
        # Otherwise, do some fancy
        if paginator.num_pages <= 10:
            page_range = range(paginator.num_pages)
        else:
            # Insert "smart" pagination links, so that there are always ON_ENDS
            # links at either end of the list of pages, and there are always
            # ON_EACH_SIDE links at either end of the "current page" link.
            page_range = []
            if page_num > (ON_EACH_SIDE + ON_ENDS):
                page_range += [
                    *range(0, ON_ENDS), '.',
                    *range(page_num - ON_EACH_SIDE, min(page_num + 1, paginator.num_pages)),
                ]
            else:
                page_range.extend(range(0, min(page_num + 1, paginator.num_pages)))

            if page_num < (paginator.num_pages - ON_EACH_SIDE - ON_ENDS - 1):
                page_range += [
                    *range(page_num + 1, page_num + ON_EACH_SIDE + 1), '.',
                    *range(paginator.num_pages - ON_ENDS, paginator.num_pages)
                ]
            else:
                page_range.extend(range(page_num + 1, paginator.num_pages))

        links = []

        for item in page_range:

            if item == ".":
                links.append("...")
                continue

            page_num = item + 1

            if page_num == page.number:
                links.append(format_html('<span class="this-page">{}</span>', page_num))
            else:
                end = mark_safe(' class="end"') if item == paginator.num_pages - 1 else ''
                links.append(
                    format_html(
                        '<a href="?{}"{}>{}</a>',
                        self.get_query_string(**{self.page_var: page_num}),
                        end,
                        page_num
                    )
                )

        return mark_safe('<span class="paginator">' + " ".join(links) + '</span>')

    def __bool__(self):
        return len(self.object_list) > 0

    def __str__(self):
        context = self.get_context_data()
        return get_template(self.template_name).render(context)
