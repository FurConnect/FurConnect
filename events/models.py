from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

class Convention(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    location = models.CharField(max_length=200)
    banner_image = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Check if this is a new convention
        if not self.pk:
            # If there's already a convention, raise an error
            if Convention.objects.exists():
                raise ValidationError("Only one convention can exist at a time. Please edit the existing convention instead.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['start_date']

class ConventionDay(models.Model):
    convention = models.ForeignKey(Convention, on_delete=models.CASCADE, related_name='days')
    date = models.DateField()
    description = models.TextField(blank=True)

    def __str__(self):
        # Display format as Month Day, Year
        return self.date.strftime('%B %d, %Y')

    class Meta:
        ordering = ['date']
        unique_together = ['convention', 'date']

class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default='#007bff', help_text="Tag color in hex format (e.g., #007bff)")

    def __str__(self):
        return self.name

class PanelTag(models.Model):
    panel = models.ForeignKey('Panel', on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    priority = models.IntegerField(default=0, help_text="Priority of the tag (lower number = higher priority)")

    class Meta:
        ordering = ['priority']
        unique_together = ['panel', 'tag']

class PanelHostOrder(models.Model):
    panel = models.ForeignKey('Panel', on_delete=models.CASCADE)
    host = models.ForeignKey('PanelHost', on_delete=models.CASCADE)
    priority = models.IntegerField(default=0, help_text="Priority of the host (lower number = higher priority)")

    class Meta:
        ordering = ['priority']
        unique_together = ['panel', 'host']

class Panel(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    convention_day = models.ForeignKey(ConventionDay, on_delete=models.CASCADE, related_name='panels')
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.ForeignKey('Room', on_delete=models.SET_NULL, null=True, blank=True, related_name='panels')
    tags = models.ManyToManyField(Tag, through=PanelTag, related_name='panels', blank=True)
    host = models.ManyToManyField('PanelHost', through=PanelHostOrder, related_name='panels', blank=True)
    cancelled = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False, verbose_name="Featured Event")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.convention_day.date}"

    class Meta:
        ordering = ['start_time']

    def get_ordered_hosts(self):
        """Get hosts ordered by their priority in PanelHostOrder"""
        return self.host.all().order_by('panelhostorder__priority')

class PanelHost(models.Model):
    name = models.CharField(max_length=100)
    image = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Room(models.Model):
    name = models.CharField(max_length=100)
    convention = models.ForeignKey(Convention, on_delete=models.CASCADE, related_name='rooms')

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ['name', 'convention']
