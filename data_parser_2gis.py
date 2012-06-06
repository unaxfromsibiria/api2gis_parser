# -*- coding: utf-8 -*-
'''
Created on 29.05.2012

@author: unax
'''
import re
import urllib2
from django.utils import simplejson
import itertools
import time

API_VERSION='1.3'
_accept_chars=u'цукенгшщзхфвапролджэячсмитбю'

class Parser2gis(object):
    __key=None
    __opener=None
    
    def __init__(self,key):
        self.__key=str(key)
        self.__opener = urllib2.build_opener()
        self.__opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.8 (KHTML, like Gecko) Chrome/17.0.942.0 Safari/535.8')]
    
    def get_city(self, city_name):
        if not isinstance(city_name, unicode):
            return None
        url=u"http://catalog.api.2gis.ru/city/list?version=%s&key=%s&where=%s" % (API_VERSION,
                                                                                  self.__key,
                                                                                  urllib2.quote( city_name.encode('utf8') ) )
        data=simplejson.loads(self.__opener.open(url).read(), encoding='utf-8')
        if 'error_message' in data:
            return { 'error' : data.get('error_message')  }
        if 'result' in data:
            for city in data['result']:
                if city and city.get('name') == city_name:
                    return city
        return None
    
    def get_city_polygon(self, city_id):
        if not isinstance(city_id, int) or city_id<1:
            return None
        url=u"http://catalog.api.2gis.ru/geo/get?version=%s&key=%s&id=%d&output=json" % (API_VERSION, self.__key, city_id)
        data=simplejson.loads(self.__opener.open(url).read(), encoding='utf-8')
        if 'error_message' in data:
            return { 'error' : data.get('error_message') }
        
        for city_data in data.get('result'):
            if int(city_data.get('id')) == city_id:
                return [ float(point) for point in re.findall('\d+[\.]\d+', city_data.get('selection'))  ]
        return None
    
    def get_rect(self, polygon):
        if isinstance(polygon,list) and len(polygon)>1:
            min_x, min_y = 100000000, 100000000
            max_x, max_y = 0, 0
            for i in range(0,len(polygon)-1,2):
                x=polygon[i]
                y=polygon[i+1]
                if x>max_x: max_x=x
                if x<min_x: min_x=x
                if y>max_y: max_y=y
                if y<min_y: min_y=y
            
            return (min_x, min_y, max_x-min_x, max_y-min_y)
        return None
    
    def get_grid(self, rect, step=0.1):
        x,y,w,h=rect
        dx=w*step
        dy=h*step
        gridx,gridy=[],[]
        for i in range(int(1/step)):
            gridx.append(x + i*dx)
            gridy.append(y + i*dy)
        return list(itertools.product(gridx,gridy))
    
    def city_grid(self,city_id, step=0.1):
        rect=self.get_rect(self.get_city_polygon(city_id))
        if rect:
            return self.get_grid(rect,step)
        return None
    
    def get_district(self, point):
        x,y=point
        url=u"http://catalog.api.2gis.ru/geo/search?q=%s,%s&key=%s&version=%s&output=json&types=district&format=short" % (str(x),
                                                                                                                         str(y),
                                                                                                                         self.__key,
                                                                                                                         API_VERSION)
        data=simplejson.loads(self.__opener.open(url).read(), encoding='utf-8')
        if 'result' in data:
            return [ district for district in data.get('result') ]
        return None

    def find_district_by_grid(self, city_name, grid_step=0.1, delay=0.1):
        city=self.get_city(city_name)
        if city is None or city.get('id') is None:
            return {'error' : u'city %s no found in 2gis' % city_name }
        
        grid_points=self.city_grid(int(city.get('id')), grid_step)
        if grid_points is None or len(grid_points)<1:
            return {'error' : u'city %s no found coordinates' % city_name }
        unique_id=[]
        res=[]
        for point in grid_points:
            time.sleep(delay)
            districts=self.get_district(point)
            if districts and len(districts)>0:
                for district in districts:
                    id=int(district.get('id'))
                    if not(id in unique_id):
                        unique_id.append(id)
                        res.append(district.get('short_name'))
        del unique_id
        return res
    
    def find_district_by_alphabet(self, city_name, delay=0.05):
        if not isinstance(city_name, unicode):
            return None
        params = (urllib2.quote( city_name.encode('utf8') ), self.__key, API_VERSION, )
        url=u"http://catalog.api.2gis.ru/geo/search?q=%s&key=%s&version=%s&output=json&types=city&limit=1&format=short" % params
        data=simplejson.loads(self.__opener.open(url).read(), encoding='utf-8')
        if 'error_message' in data:
            return { 'error' : data.get('error_message') }
        res=[]
        if 'result' in data:
            project_id=data.get('result')[0].get('project_id')
            for first_char in _accept_chars:
                time.sleep(delay)
                params = (urllib2.quote( (u"район %s" % first_char).encode('utf8') ), self.__key, API_VERSION, project_id)
                url=u"http://catalog.api.2gis.ru/geo/search?q=%s&key=%s&version=%s&output=json&types=district&limit=50&format=short&project=%s" % params
                data=simplejson.loads(self.__opener.open(url).read(), encoding='utf-8')
                if 'result' in data:
                    for district in data.get('result'):
                        res.append(district.get('short_name'))
        if len(res)>0:
            return res
        return None
    
    def find_metro_station(self, city_name, delay=0.05):
        if not isinstance(city_name, unicode): return None
        params = (urllib2.quote( city_name.encode('utf8') ), self.__key, API_VERSION, )
        url=u"http://catalog.api.2gis.ru/geo/search?q=%s&key=%s&version=%s&output=json&types=city&limit=1&format=short" % params
        data=simplejson.loads(self.__opener.open(url).read(), encoding='utf-8')
        if 'error_message' in data:
            return { 'error' : data.get('error_message') }
        res=[]
        r=re.compile(u'[Мм]етро[ ]{1}')
        if 'result' in data:
            project_id=data.get('result')[0].get('project_id')
            for first_char in _accept_chars:
                time.sleep(delay)
                params = (urllib2.quote( (u"метро %s" % first_char).encode('utf8') ), self.__key, API_VERSION, project_id)
                url=u"http://catalog.api.2gis.ru/geo/search?q=%s&key=%s&version=%s&output=json&types=station_platform&limit=20&format=short&project=%s" % params
                data=simplejson.loads(self.__opener.open(url).read(), encoding='utf-8')
                if 'result' in data:
                    for metro in data.get('result'):
                        name=r.sub(' ', metro.get('short_name')).strip()
                        if not (name in res) and len(name)>2:
                            res.append(name)
        if len(res)>1:
            return res
        return None

    def free_search(self, city_name, text, object_type):
        if not isinstance(text, unicode):
            return None
        params = (urllib2.quote( city_name.encode('utf8') ), self.__key, API_VERSION, )
        url=u"http://catalog.api.2gis.ru/geo/search?q=%s&key=%s&version=%s&output=json&types=city&limit=1&format=short" % params
        data=simplejson.loads(self.__opener.open(url).read(), encoding='utf-8')
        if 'error_message' in data:
            return { 'error' : data.get('error_message') }

        if 'result' in data:
            project_id=data.get('result')[0].get('project_id')
            params = (urllib2.quote( text.encode('utf8') ), self.__key, API_VERSION, object_type, project_id)
            url=u"http://catalog.api.2gis.ru/geo/search?q=%s&key=%s&version=%s&output=json&types=%s&limit=1000&format=short&project=%s" % params
            data=simplejson.loads(self.__opener.open(url).read(), encoding='utf-8')
            if 'result' in data:
                return  data.get('result')
            else:
                return data
        return None
