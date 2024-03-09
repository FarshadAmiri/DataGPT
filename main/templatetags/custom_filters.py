from django.utils.safestring import mark_safe
from django import template
from datetime import datetime, timedelta, timezone
import pytz
import json ,os

register = template.Library()

@register.filter
def fa_digits(text):
    persian_digits = ['۰','۱','۲','۳','۴','۵','۶','۷','۸','۹']
    english_digits = ['0','1','2','3','4','5','6','7','8','9']
    for i in range(len(english_digits)):
        text = str(text).replace(english_digits[i], persian_digits[i])
    return text


@register.filter(is_safe=True)
def js(obj):
    return mark_safe(json.dumps(obj))


@register.filter(name='has_group') 
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists() 


@register.filter
def get_dict_value(dictionary, key):
    return dictionary.get(int(key), "")


@register.filter
def path_end_part(path):
    return os.path.basename(path)


@register.filter
def time_template(timestamp):
    ir_tz = pytz.timezone('Asia/Tehran')
    timestamp = timestamp.astimezone(ir_tz)
    today_date = datetime.today().date()
    timestamp_date = timestamp.date()
    output = None
    if today_date == timestamp_date:
        # today
        output = f"Today  {timestamp.strftime('%H:%M')}"
    elif today_date == timestamp_date + timedelta(days=1):
        # yesterday
        output = f"Yesterday  {timestamp.strftime('%H:%M')}"
    else:
        output = f"{timestamp.strftime('%d %b')}   {timestamp.strftime('%H:%M')}"
    return output