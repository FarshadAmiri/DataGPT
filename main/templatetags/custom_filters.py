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
        output = timestamp.strftime("%Y/%m/%d  %H:%M")
    return output


@register.filter(name='markdown_to_html')
def markdown_to_html(text):
    """
    Convert markdown formatting to HTML
    Supports: headings (# ## ###), bold (**text**), lists (- item)
    """
    if not text:
        return ""
    
    lines = text.split('\n')
    # Remove leading empty lines to avoid blank space at the top
    while lines and not lines[0].strip():
        lines.pop(0)
    html_lines = []
    in_list = False
    
    for line in lines:
        # Close list if we were in one and current line is not a list item
        if in_list and not line.strip().startswith('-'):
            html_lines.append('</ul>')
            in_list = False
        
        # Headers (####, ###, ##, #)
        if line.strip().startswith('####'):
            content = line.replace('####', '', 1).strip()
            content = convert_bold(content)
            html_lines.append(f'<h4 style="color: #ffc107; margin-top: 15px; margin-bottom: 8px; font-size: 1.1em;">{content}</h4>')
        elif line.strip().startswith('###'):
            content = line.replace('###', '', 1).strip()
            content = convert_bold(content)
            html_lines.append(f'<h3 style="color: #17a2b8; margin-top: 20px; margin-bottom: 10px; font-size: 1.3em;">{content}</h3>')
        elif line.strip().startswith('##'):
            content = line.replace('##', '', 1).strip()
            content = convert_bold(content)
            html_lines.append(f'<h2 style="color: #28a745; margin-top: 25px; margin-bottom: 12px; font-size: 1.5em;">{content}</h2>')
        elif line.strip().startswith('#'):
            content = line.replace('#', '', 1).strip()
            content = convert_bold(content)
            html_lines.append(f'<h1 style="color: #007bff; margin-top: 30px; margin-bottom: 15px; font-size: 1.8em;">{content}</h1>')
        # List items
        elif line.strip().startswith('-'):
            if not in_list:
                html_lines.append('<ul style="margin-left: 20px; color: #e0e0e0;">')
                in_list = True
            content = line.strip()[1:].strip()  # Remove the '-'
            content = convert_bold(content)
            html_lines.append(f'<li style="margin-bottom: 5px;">{content}</li>')
        # Regular text
        else:
            content = convert_bold(line)
            if content.strip():  # Only add non-empty lines
                html_lines.append(f'<p style="margin: 8px 0; color: #e0e0e0; line-height: 1.6;">{content}</p>')
            else:
                html_lines.append('<br>')
    
    # Close list if still open
    if in_list:
        html_lines.append('</ul>')
    
    return mark_safe(''.join(html_lines))


def convert_bold(text):
    """
    Convert **bold** to <strong>bold</strong>
    """
    import re
    # Replace **text** with <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: #fff;">\1</strong>', text)
    return text