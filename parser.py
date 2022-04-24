#!/usr/bin/env python3

"""Simple Spbu timetable parser
"""
import sys
import argparse
import datetime
import requests
import tabulate
import dateparser
from bs4 import BeautifulSoup


def parse_args(args=sys.argv[1:]):
    """Parse arguments."""
    parser = argparse.ArgumentParser(
        description=sys.modules[__name__].__doc__)

    parser.add_argument("--date", type=str, default='', help="date to parse, format YYYY-MM-DD")
    parser.add_argument("--id", type=str, default='303104', help="group id for timetable, part of url, get one on https://timetable.spbu.ru/")
    parser.add_argument('--no-tls-verify', dest='tls_validation', action='store_false', default=True, help="disable TLS verification in requests library")
    return parser.parse_args(args)

options = parse_args()

base_url = f'https://timetable.spbu.ru/AMCP/StudentGroupEvents/Primary/{options.id}/'


if len(options.date)>0:
    try:
        datetime.datetime.strptime(options.date, '%Y-%m-%d')
        url = base_url + options.date
    except ValueError:
        print('Error prasing date format, use YYYY-MM-DD')
        sys.exit(1)
else:
    url = base_url

setcookie={'_culture': 'ru'}
r = requests.get(url, cookies=setcookie,  verify=options.tls_validation)
soup = BeautifulSoup(r.text, 'html.parser')

timetable_html = soup.find_all("div", {"class": "panel-group"})[0]

events=[]

timetable_day = soup.find_all('a', {"id": "week" })[0]['data-weekmonday']

for day in timetable_html:
    #skip '\n' lines, better approach needed
    if len(day) > 1:
        event_day = day.contents[1].find('h4').string.strip()
        for lesson in day.contents[3]:
            if len(lesson) < 2:
                continue
           #check for cancelled events first
            if len(lesson.find_all('span', {"class": "cancelled"})) > 0:
                continue

            #time
            if len(lesson.find_all('span', {"title": "Добавлено занятие"})) > 0:
                event_time = lesson.find_all('span', {"title": "Добавлено занятие"})[0].string.strip()
            elif  len(lesson.find_all('span', {"title": "Заменены дата/время"})) > 0:
                event_time = lesson.find_all('span', {"title": "Заменены дата/время"})[0].string.strip()
            else:
                event_time = lesson.find_all('span', {"title": "Время"})[0].string.strip()
            #workaround for undefined end time
            if "\u2013" in  event_time:
                event_start_string = event_day + ' ' + event_time.split('\u2013')[0]
                event_end_string = event_day + ' ' + event_time.split('\u2013')[1]
            else:
                event_start_string = event_day + ' ' + event_time
                event_end_string = event_day + ' ' + event_time

            #type and title
            if len(lesson.find_all('span', {"title": "Добавлено занятие"})):
                #title is same as time title
                event_string = lesson.find_all('span', {"title": "Добавлено занятие"})[1].string.strip()
            else:
                event_string = lesson.find_all('span', {"title": "Предмет"})[0].string.strip()
            event_title = event_string.split(',')[0].strip()
            event_type = event_string.split(',')[1].strip()

            #location
            #support for empty location or lecturer needed
            if len(lesson.find_all('div', {"title": "Места проведения занятия"})) > 0:
                event_location_string = lesson.find_all('div', {"title": "Места проведения занятия"})[0].find('span').string.strip()
            elif len(lesson.find_all('div', {"title": "Заменены места проведения занятия"})) > 0:
                event_location_string = lesson.find_all('div', {"title": "Заменены места проведения занятия"})[0].find('span').string.strip()
            else:
                event_location_string = lesson.find_all('span', {"title": "Места проведения занятия"})[0].string.strip()

            if event_location_string == 'С использованием информационно-коммуникационных технологий':
                event_location = 'Онлайн'
            elif 'Университетский проспект, д. 35' in event_location_string:
                event_location = 'ПМ ' + event_location_string.split(',')[-1]
            elif 'Университетский проспект, д. 28' in event_location_string:
                event_location = 'ММ ' + event_location_string.split(',')[-1]
            else:
                event_location = event_location_string

            #lecturers
            #support for empty location or lecturer needed
            if len(lesson.find_all('span', {"title": "Преподаватели"})) > 0:
                lecturers=lesson.find_all('span', {"title": "Преподаватели"})
                try:
                    non_person=lecturers[0].find('span', {"class": "moreinfo"})
                except:
                    pass
                if isinstance(lecturers[0].string, str):
                    event_lecturers_list = []
                    for lecturer in lecturers:
                        if len(lecturer.find_all('a')) > 0:
                            event_lecturers_list.append(lecturer.find('a').string.strip())
                elif non_person is not None:
                    event_lecturers_list = [lecturers[0].find('span', {"class": "moreinfo"}).string.strip()]
                else:
                    event_lecturers_list = [lesson.find_all('span', {"title": "Преподаватели"})[0].find('a').string.strip()]
            else:
                #here also can be multiple lecturers
                event_lecturers_list = [lesson.find_all('span', {"title": "Заменены преподаватели"})[0].find('a').string.strip()]
            event_lecturers = ", ".join(event_lecturers_list)

            #time to event
            event_start = dateparser.parse(event_start_string, languages=['ru'])
            event_end = dateparser.parse(event_end_string, languages=['ru'])
            delta = event_start - datetime.datetime.now()
            if delta.total_seconds() < 0:
                time_to_event = "passed"
            else:
                tte_days, tte_hours, tte_minutes = delta.days, delta.seconds // 3600, delta.seconds // 60 % 60
                time_to_event = f"{tte_days}:{tte_hours:02d}:{tte_minutes:02d}"

            #resulting event
            event = {
              'start': event_start,
              'D:H:M': time_to_event,
              'end': event_end,
              'type': event_type,
              'title': event_title,
              'location': event_location,
              'lecturers': event_lecturers
              }
            events.append(event)

if len(events)>0:
    print("Timetable for 7 days starting", timetable_day)
    print(tabulate.tabulate(events, headers="keys"))
else:
    print('No events found\nCheck website to be sure:', url)
