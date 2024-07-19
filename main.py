import openmeteo_requests
import requests_cache
import datetime
import pytz
import pandas as pd

from retry_requests import retry
from geopy.geocoders import Nominatim
from functools import partial
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Form, Header, Request


app = FastAPI()
url = "https://api.open-meteo.com/v1/forecast"
geolocator = Nominatim(user_agent="lalalalala")
geocode = partial(geolocator.geocode, language="ru")
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)
templates = Jinja2Templates(directory='app/templates')


@app.get('/')
def start(request: Request):
    return templates.TemplateResponse(
        '/start.html',
        {'request': request,}
    )


@app.post('/')
def get_temperature(
        request: Request,
        city: str = Form(...),
):
    location = geolocator.geocode(city)
    now: datetime = datetime.datetime.now(pytz.timezone('UTC'))
    params: dict[str,str] = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "hourly": "temperature_2m",
        'start_hour': f'{str(now)[:10]}T{str(now)[11:13]}:00',
        'end_hour': (f'{str(now+datetime.timedelta(hours=24))[:10]}T'
                     f'{str(now+datetime.timedelta(hours=24))[11:13]}:00'),
    }
    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    hourly_data = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left"
    )
    return templates.TemplateResponse(
        '/result.html',
        {
            'request': request,
            'Coordinates': f'{response.Latitude()}°N {response.Longitude()}°E',
            'Address': location.address,
            'Time': hourly_data,
            'Temperature': hourly_temperature_2m,
        },
    )
