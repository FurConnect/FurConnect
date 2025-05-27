from django import template
from django.utils import timezone
from datetime import datetime, timedelta
import re

register = template.Library()

# Define your custom template filters and tags here

@register.filter
def get_item(dictionary, key):
    """
    Retrieves an item from a dictionary using a given key.
    Add your specific implementation here if needed.
    """
    try:
        return dictionary.get(key)
    except AttributeError:
        # Handle cases where the input is not a dictionary
        return None 

@register.filter
def format_date(date):
    """
    Formats a date in a consistent way across the application.
    """
    if not date:
        return ""
    return date.strftime("%B %d, %Y")

@register.filter
def format_time(time):
    """
    Formats a time in a consistent way across the application.
    """
    if not time:
        return ""
    return time.strftime("%I:%M %p")

@register.filter
def is_future(date):
    """
    Checks if a date is in the future.
    """
    if not date:
        return False
    return date > timezone.now()

@register.filter
def is_past(date):
    """
    Checks if a date is in the past.
    """
    if not date:
        return False
    return date < timezone.now()

@register.filter
def is_current(date):
    """
    Checks if a date is today.
    """
    if not date:
        return False
    today = timezone.now().date()
    return date.date() == today

@register.filter
def time_until(date):
    """
    Returns a human-readable string of time until the event.
    """
    if not date:
        return ""
    now = timezone.now()
    delta = date - now
    
    if delta.days > 0:
        return f"{delta.days} days"
    elif delta.seconds >= 3600:
        hours = delta.seconds // 3600
        return f"{hours} hours"
    elif delta.seconds >= 60:
        minutes = delta.seconds // 60
        return f"{minutes} minutes"
    else:
        return "now"

@register.filter
def duration(start_time, end_time):
    """
    Calculates and formats the duration between two times.
    """
    if not start_time or not end_time:
        return ""
    
    duration = end_time - start_time
    hours = duration.seconds // 3600
    minutes = (duration.seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
    else:
        return f"{minutes}m"

@register.filter
def is_same_day(date1, date2):
    """
    Checks if two dates are on the same day.
    """
    if not date1 or not date2:
        return False
    return date1.date() == date2.date()

@register.filter
def is_consecutive_day(date1, date2):
    """
    Checks if two dates are consecutive days.
    """
    if not date1 or not date2:
        return False
    return (date2.date() - date1.date()).days == 1

@register.filter
def format_date_range(start_date, end_date):
    """
    Formats a date range in a user-friendly way.
    """
    if not start_date or not end_date:
        return ""
    
    if start_date.date() == end_date.date():
        return format_date(start_date)
    elif start_date.year == end_date.year:
        if start_date.month == end_date.month:
            return f"{start_date.strftime('%B %d')} - {end_date.strftime('%d, %Y')}"
        else:
            return f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"
    else:
        return f"{format_date(start_date)} - {format_date(end_date)}"

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

@register.filter
def is_light_color(color):
    """
    Determines if a color is light or dark.
    Returns True for light colors, False for dark colors.
    """
    if not color:
        return True
    
    # Remove any non-hex characters
    color = re.sub(r'[^0-9a-fA-F]', '', color)
    
    # If color is not a valid hex, return True as default
    if len(color) != 6:
        return True
    
    # Convert hex to RGB
    r, g, b = hex_to_rgb(color)
    
    # Calculate relative luminance using the formula:
    # L = 0.2126 * R + 0.7152 * G + 0.0722 * B
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    
    # Return True if the color is light (luminance > 0.5)
    return luminance > 0.5 