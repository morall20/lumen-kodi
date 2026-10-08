"""Configurable dotted-field adapter for a permitted JSON announcement API."""
import json
import re
from .rss import timestamp


def field(value, path):
    if not path:
        return value
    if len(path)>120 or not re.fullmatch(r'[A-Za-z0-9_.]+',path):
        raise ValueError('Use a dotted JSON field path')
    for key in path.split('.'):
        value=value.get(key) if isinstance(value,dict) else None
    return value


def parse(raw, config):
    rows=field(json.loads(raw),config.get('items_field','items'))
    if not isinstance(rows,list):
        raise ValueError('API items field must contain a list')
    result=[]
    for row in rows[:50]:
        title=field(row,config.get('title_field','title'))
        if not isinstance(title,str) or not title.strip():
            continue
        ids={}
        for kind in ('tmdb','imdb','tvdb'):
            path=config.get(kind+'_field')
            value=field(row,path) if path else None
            if kind=='imdb' and re.fullmatch(r'tt\d{5,12}',str(value)):
                ids[kind]=value
            elif kind!='imdb' and str(value).isdigit() and 0<int(value)<2**63:
                ids[kind]=int(value)
        result.append({'title':title[:500], 'published':timestamp(field(row,config.get('date_field','published'))), 'ids':ids})
    return result
