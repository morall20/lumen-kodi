import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def timestamp(value):
    try:
        date=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except ValueError:
        try:
            date=parsedate_to_datetime(str(value))
        except (ValueError,TypeError,OverflowError):
            return 0
    try:
        return (date if date.tzinfo else date.replace(tzinfo=timezone.utc)).timestamp()
    except (ValueError,OverflowError,OSError):
        return 0


def parse(raw, config=None):
    # Reject DTD/entity declarations, including UTF-16/32 encodings with NULs.
    safety=raw.replace(b'\x00',b'').upper()
    if b'<!DOCTYPE' in safety or b'<!ENTITY' in safety:
        raise ValueError('DTD/entity declarations are not supported')
    root=ET.fromstring(raw)
    if root.tag.split('}')[-1] not in ('rss','feed','RDF'):
        raise ValueError('Expected RSS or Atom XML')
    result=[]
    for entry in root.iter():
        if entry.tag.split('}')[-1] not in ('item','entry'):
            continue
        fields={child.tag.split('}')[-1]:child for child in entry}
        title=''.join(fields['title'].itertext()).strip() if 'title' in fields else ''
        if not title:
            continue
        dates=[fields[k].text for k in ('published','pubDate','date','updated') if k in fields]
        result.append({'title':title[:500], 'published':timestamp(dates[0]) if dates else 0, 'ids':{}})
        if len(result)>=50:
            break
    return result
