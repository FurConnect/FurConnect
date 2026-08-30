from django import forms
from django.conf import settings
from datetime import timedelta, datetime
from .models import Convention, ConventionDay, Panel, PanelHost, Tag, Room, PanelHostOrder, PanelTag

class ConventionForm(forms.ModelForm):
    hotel_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '})
    )
    address = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '})
    )
    city = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '})
    )
    state = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '})
    )
    country = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ' '})
    )
    banner_image = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    class Meta:
        model = Convention
        fields = ['name', 'description', 'start_date', 'end_date', 'banner_image']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': ' ',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': ' ',
                'rows': 3,
                'required': False
            }),
            'start_date': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'text',
                'required': True
            }),
            'end_date': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'text',
                'required': True
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Populate location fields
            if self.instance.location:
                location_parts = [part.strip() for part in self.instance.location.split(',')]
                # Assign parts based on the order in the clean method
                self.fields['hotel_name'].initial = location_parts[0] if len(location_parts) > 0 else ''
                self.fields['address'].initial = location_parts[1] if len(location_parts) > 1 else ''
                self.fields['city'].initial = location_parts[2] if len(location_parts) > 2 else ''
                self.fields['state'].initial = location_parts[3] if len(location_parts) > 3 else ''
                self.fields['country'].initial = location_parts[4] if len(location_parts) > 4 else ''

            # Populate date fields
            if self.instance.start_date:
                self.fields['start_date'].initial = self.instance.start_date
            if self.instance.end_date:
                self.fields['end_date'].initial = self.instance.end_date

    def clean(self):
        cleaned_data = super().clean()
        # Combine location fields into a single string
        location_parts = []
        if cleaned_data.get('hotel_name'):
            location_parts.append(cleaned_data['hotel_name'])
        if cleaned_data.get('address'):
            location_parts.append(cleaned_data['address'])
        if cleaned_data.get('city'):
            location_parts.append(cleaned_data['city'])
        if cleaned_data.get('state'):
            location_parts.append(cleaned_data['state'])
        if cleaned_data.get('country'):
            location_parts.append(cleaned_data['country'])
        
        # Store the combined location in cleaned_data
        cleaned_data['location'] = ', '.join(location_parts)
        return cleaned_data

    def save(self, commit=True):
        # Get the model instance from the form
        instance = super().save(commit=False)
        
        # Assign the combined location from cleaned_data to the instance's location field
        instance.location = self.cleaned_data['location']

        # Check if the instance is new or being updated
        is_new = instance.pk is None

        # Call the model instance's save method to ensure it has a PK if commit is True
        if commit:
            instance.save()

            # Get start and end dates from cleaned data
            start_date = self.cleaned_data.get('start_date')
            end_date = self.cleaned_data.get('end_date')

            if start_date and end_date and start_date <= end_date:
                # Get existing days
                existing_days = {day.date: day for day in instance.days.all()}
                
                # Create a set of all dates in the new range
                new_dates = set()
                current_date = start_date
                while current_date <= end_date:
                    new_dates.add(current_date)
                    current_date += timedelta(days=1)

                # Delete days that are outside the new date range
                for date, day in existing_days.items():
                    if date not in new_dates:
                        day.delete()

                # Create new days for dates that don't exist
                for date in new_dates:
                    if date not in existing_days:
                        ConventionDay.objects.create(convention=instance, date=date)

        return instance

class ConventionDayForm(forms.ModelForm):
    class Meta:
        model = ConventionDay
        fields = ['date', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class PanelForm(forms.ModelForm):
    convention_day = forms.ModelChoiceField(
        queryset=ConventionDay.objects.none(), # Start with an empty queryset
        label="Day",
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True # Assuming a day is required for a panel
    )
    room = forms.ModelChoiceField(
        queryset=Room.objects.none(), # Start with an empty queryset
        label="Room",
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        empty_label="Select a room..."
    )

    class Meta:
        model = Panel
        fields = ['title', 'description', 'convention_day', 'start_time', 'end_time', 'room', 'tags', 'host', 'is_featured', 'cancelled']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'convention_day': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'room': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'host': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'cancelled': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        convention = kwargs.pop('convention', None)
        super().__init__(*args, **kwargs)

        if convention:
            self.fields['convention_day'].queryset = ConventionDay.objects.filter(convention=convention).order_by('date')
            self.fields['room'].queryset = Room.objects.filter(convention=convention).order_by('sort_order', 'name')
        elif self.instance and self.instance.pk and getattr(self.instance, 'convention_day', None):
            convention = self.instance.convention_day.convention
            self.fields['convention_day'].queryset = ConventionDay.objects.filter(convention=convention).order_by('date')
            self.fields['room'].queryset = Room.objects.filter(convention=convention).order_by('sort_order', 'name')

        self.fields['tags'].queryset = Tag.objects.all().order_by('name')
        self.fields['host'].queryset = PanelHost.objects.all().order_by('name')
        if self.instance and self.instance.pk:
            self.initial['tags'] = list(
                self.instance.tags.all().order_by('paneltag__priority').values_list('pk', flat=True)
            )
            self.initial['host'] = list(
                self.instance.host.all().order_by('panelhostorder__priority').values_list('pk', flat=True)
            )

    def save(self, commit=True):
        panel = super().save(commit=False)
        if commit:
            host_order = self._posted_ids('host')
            tag_order = self._posted_ids('tags')
            panel.save()
            self.save_m2m()
            self._apply_ordered_relations(panel, host_order, tag_order)
        return panel

    def _posted_ids(self, field_name):
        data = self.data
        if hasattr(data, 'getlist'):
            values = data.getlist(field_name)
        else:
            value = data.get(field_name, [])
            if value in (None, ''):
                values = []
            elif isinstance(value, (list, tuple)):
                values = list(value)
            else:
                values = [value]
        return [str(value).strip() for value in values if str(value).strip()]

    def _apply_ordered_relations(self, panel, host_order, tag_order):
        for index, host_id in enumerate(host_order):
            PanelHostOrder.objects.update_or_create(
                panel=panel,
                host_id=host_id,
                defaults={'priority': index},
            )
        PanelHostOrder.objects.filter(panel=panel).exclude(host_id__in=host_order).delete()

        for index, tag_id in enumerate(tag_order):
            PanelTag.objects.update_or_create(
                panel=panel,
                tag_id=tag_id,
                defaults={'priority': index},
            )
        PanelTag.objects.filter(panel=panel).exclude(tag_id__in=tag_order).delete()

class PanelHostForm(forms.ModelForm):
    image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = PanelHost
        fields = ['name', 'concat_user_id']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'concat_user_id': forms.TextInput(attrs={
                'class': 'form-control',
                'inputmode': 'numeric',
                'placeholder': 'ConCat user ID',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.CONCAT_ENABLED:
            self.fields.pop('concat_user_id', None)

class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control jscolor'}),
        }

class CSVImportForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload a CSV file with panel information. Required columns: title, description, date, start_time, end_time, room, tags, hosts',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'})
    )
    convention = forms.ModelChoiceField(
        queryset=Convention.objects.all(),
        label='Convention',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        if not csv_file.name.endswith('.csv'):
            raise forms.ValidationError('File must be a CSV file')
        return csv_file 