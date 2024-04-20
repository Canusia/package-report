import logging
from django import forms
from django.conf import settings
from django.forms import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils.module_loading import import_string

from report.models.report import Report

LOGGER = logging.getLogger(__name__)

class AddReportForm(forms.ModelForm):
    description = forms.CharField(
        widget=forms.Textarea()
    )

    class Meta:
        model = Report
        fields = [
            'app',
            'name',
            'title',
            'description',
            'categories',
            'available_for'
        ]

        labels = {
            'available_for':'Available For'
        }

    def clean_name(self):
        data = self.cleaned_data

        report_name = self.cleaned_data['name']
        try:            
            reports_path = data.get('app', 'cis') + '.reports'
            report_class = import_string(f'{reports_path}.{report_name}.{report_name}')
            return report_name
        except (ModuleNotFoundError, ImportError) as e:
            LOGGER.error(e)
            raise ValidationError(
                _(f"The report name was not found in {report_class}. Please check and try again")
            )

    def clean(self):
        cleaned_data = super().clean()

        return cleaned_data
