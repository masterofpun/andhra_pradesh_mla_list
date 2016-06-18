#Andhra Pradesh

import sqlite3
import os
from bs4 import BeautifulSoup as Soup
import json, requests, re
import datetime
from fuzzywuzzy import fuzz

DB_FILE = 'data.sqlite'

rex = re.compile(r'\s+')
numb = re.compile(r'[^0-9]')
rdate = re.compile(r'[^a-z0-9]')
const = re.compile(r'[^a-z0-9\-]')

conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute('drop table IF EXISTS data')
c.execute('create table data (birth_date,"+children","+constituency",contact_details,"+education","+education_details",email,image,images,link,"+marital_status",name,memberOf,other_names,"+place_of_birth","+profession",source,"+spouse")')

parties = {'APCC':'Andhra Pradesh Congress Party',
           'TDP':'Telugu Desam Party',
           'PR':'Praja Rajyam',
           'BJP':'Bharatiya Janata Party',
           'INDPT':'Indipendent',
           'YSRCP':'YSR Congress Party'}

def words2date(bdate):
    bdate = clean(rdate.sub(' ',bdate.lower()))
    if len(bdate)<2:
        return None
    bdate = bdate.replace('febuary','february')
    month = ['january','february','march','april','may','june','july','august','september','october','november','december']
    bdate = bdate.split(' ')
    date = datetime.date(int(bdate[2]),int(month.index(bdate[1])+1),int(numb.sub('',bdate[0])))
    return date.isoformat()

def text2int(textnum, numwords={}):
    if not numwords:
      units = [
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen",
      ]

      tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

      scales = ["hundred", "thousand", "million", "billion", "trillion"]

      numwords["and"] = (1, 0)
      for idx, word in enumerate(units):    numwords[word] = (1, idx)
      for idx, word in enumerate(tens):     numwords[word] = (1, idx * 10)
      for idx, word in enumerate(scales):   numwords[word] = (10 ** (idx * 3 or 2), 0)

    current = result = 0
    for word in textnum.split():
        if word not in numwords:
            return 0

        scale, increment = numwords[word]
        current = current * scale + increment
        if scale > 100:
            result += current
            current = 0
    return result + current

def num(s):
    s = numb.sub(' ',s)
    s = clean(s)
    if s is None:
        return 0
    return int(s)

def clean(s):
    return rex.sub(' ',s).strip()

def extract(data,first,second):
    if first not in data or second not in data:
        return None
    data = data.split(first)[1]
    if second not in data:
        return None
    return clean(data.split(second,1)[0])
    
def getDate(s):
    d = extract(s,'Date of Birth </b><br />','</li>')
    if d is None:
        return None
    d = numb.sub(' ',d)
    d = clean(d)
    if d is None or len(d)<8:
        print('couldn\'t parse',d)
        return None
    date = d.split(' ')
    return datetime.date(int(date[2]),int(date[1]),int(date[0])).isoformat()

req = requests.get('http://aplegislature.org/web/aplegislature/memberurl')
soup = Soup(req.text,'html.parser')

mnlink = 'http://www.myneta.info/delhi2015/index.php?action=show_winners&sort=default'
myneta = Soup(requests.get(mnlink).text,'html.parser')

for row in soup.find_all('li'):
    if 'cbp-vm-image photo-inner' not in str(row):
        continue
    member = {}
    
    link = row.find('a')['href']
    raw_details = requests.get(link).text
    details = Soup(raw_details,'html.parser')

    const = row.find('div', class_="cbp-vm-price const_name").text.split('.')
    constituency = {
        'name':clean(const[1]).title(),
        'identifier':num(clean(const[0])),
        'classification':'constituency',
        '+state':'Andhra Pradesh'
        },

    og_name = clean(row.find('font',class_='cbp-vm-title mem_name').text).title()
    name = og_name
    neta = None

    names = []
    for tr in myneta.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds)!=8:
            continue
        names.append(tr)
        if name.lower() in clean(tds[1].text).lower():
            neta = tr
            break
        
    if neta is None:
        na = clean(name.replace('.',' '))
        na = ' '.join(name.split()[1:])
        for tr in names:
            tds = tr.find_all('td')
            if na.lower() in clean(tds[1].text).lower():
                neta = tr
                break
            
    if neta is None:
        old_fuz = -1
        new_name = ''
        for tr in names:
            tds = tr.find_all('td')
            new_fuz = fuzz.ratio(name.lower(),clean(tds[1].text).lower())
            if new_fuz>old_fuz:
                neta = tr
                old_fuz = new_fuz
                new_name = clean(tds[1].text).title()
        name = new_name
    
    party_id = clean(row.find('div',class_='cbp-vm-icon cbp-vm-add').text)
    party = ''
    if party_id not in parties:
        party = 'Indipendent'
        party_id = 'INDPT'
    else:
        party = parties[party_id]
    spouse = extract(raw_details,'Spouse Name</b> <br />','</li>')
    
    member = {
    'other_names' : [
        {
            'name' : og_name,
            'note' : 'Name with prefix'
         }
        ],
    'name' : name,
    'email' : '',
    'birth_date' : getDate(raw_details),
    'image' : row.find('img')['src'],
    'images' : [{'url':row.find('img')['src']}],
    '+constituency' : constituency,
    'memberOf' : {
        'id':party_id,
        'name':party
        },
    '+education': clean(neta.find_all('td')[5].text),
    '+education_details' : [extract(raw_details,'Qualification</b> <br />','</li>')],
    '+profession' : extract(raw_details,'Profession</b> <br />','</li>'),
    '+marital_status' : True if spouse is not None else False,
    '+spouse' : spouse.title(),
    'source' : 'aplegislature.org',
    'links' : [{'url':link,'note':'aplegislature.org'}]
    }
    contact_details = [
            {
                'type':'address',
                'label':'Residential address',
                'value':extract(raw_details,'Address 1: </span> <p>','</p>')
            }]
    phones = extract(raw_details,'glyphicon-phone mr5"></i>','</p>')
    for phone in phones.split(';'):
        if len(phone)>4:
            contact_details.append({
                    'type':'phone',
                    'label':'phone/mobile',
                    'value':clean(phone)
                })
    member['contact_details']=contact_details
    print(json.dumps(member,sort_keys=True,indent=4))
    data = [
        member['birth_date'],
        None,
        json.dumps(member['+constituency'],sort_keys=True),
        json.dumps(member['contact_details'],sort_keys=True),
        member['+education'],
        json.dumps(member['+education_details'],sort_keys=True),
        member['email'],
        member['image'],
        json.dumps(member['images'],sort_keys=True),
        json.dumps(member['links'],sort_keys=True),
        json.dumps(member['+marital_status'],sort_keys=True),
        member['name'],
        json.dumps(member['memberOf'],sort_keys=True),
        json.dumps(member['other_names'],sort_keys=True),
        None,
        json.dumps(member['+profession'],sort_keys=True),
        member['source'],
        member['+spouse']
        ]
    c.execute('insert into data values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',data)
conn.commit()
c.close()
