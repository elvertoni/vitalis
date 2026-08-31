"""
Data isolation layer.

Security requirement number one: a user must never reach another user's records.
Isolation is enforced here, in one place, instead of being repeated in every view.

Every domain CBV inherits from ``OwnerQuerySetMixin``. Views that write also inherit
from ``OwnerFormMixin``, which stamps the owner on creation and narrows the related
field choices, so a crafted POST cannot attach someone else's object.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models


class OwnerQuerySetMixin(LoginRequiredMixin):
    """
    Restricts the view queryset to rows owned by the logged in user.

    Applies to list, detail, update and delete alike: a detail view reached by primary
    key returns 404 for someone else's row, because the row is simply not in the
    queryset.
    """

    owner_field = 'user'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{self.owner_field: self.request.user})


class OwnerFormMixin:
    """
    Stamps the owner on create and keeps related field choices inside the owner's data.

    Without the second part, a user could post the primary key of another user's record
    into a foreign key field and link to it. Choices are narrowed for every relation
    whose target model carries an owner column.
    """

    owner_field = 'user'

    def form_valid(self, form):
        setattr(form.instance, self.owner_field, self.request.user)
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name, field in form.fields.items():
            queryset = getattr(field, 'queryset', None)
            if queryset is None:
                continue
            model = queryset.model
            try:
                model._meta.get_field(self.owner_field)
            except models.FieldDoesNotExist:
                continue
            field.queryset = queryset.filter(**{self.owner_field: self.request.user})
        return form
