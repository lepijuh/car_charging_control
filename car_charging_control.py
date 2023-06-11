import datetime
import schedule
import time
import pytz
import requests

# PSA Car Control requests used here:

# 1 Get the car state :
# http://localhost:5000/get_vehicleinfo/YOURVIN

# 2 Change charge hour (for example: set it to 22h30)
# http://localhost:5000/charge_hour?vin=YOURVIN&hour=22&minute=30


vin = 'YOURVIN' # Car VIN as a string
set_time = '18:30' # When the prices are checked and the start time for the car set
charge_hours = 5 # charge time in hours
start_time = '02:00' # default start time if there is some problems getting the prices etc.
charging_current = 13 # Charging current per phase in A. Three phases assumed to be used.
baseurl = '192.168.0.200' # IP for the psa-car-control
finnish_tz = pytz.timezone('Europe/Helsinki') # Set the time zone to Finnish time (Eastern European Time) for datetime


def convert_to_minutes(time_str):
    if ':' in time_str:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    elif 'PT' in time_str:
        time_str = time_str[2:]
        hours = 0
        minutes = 0
        if 'H' in time_str:
            hours_str, time_str = time_str.split('H')
            hours = int(hours_str)
        if 'M' in time_str:
            minutes_str, _ = time_str.split('M')
            minutes = int(minutes_str)
        return hours * 60 + minutes


def check_needed_charge_time(baseurl, vin, charging_current):
    max_attempts = 5
    attempt = 1
    response = None
    while attempt <= max_attempts:
        response = requests.get('http://'+baseurl+':5000/get_vehicleinfo/'+vin)
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' INFO: Request URL:', response.request.url)
        print(current_time,' INFO: Response Status Code:', response.status_code)
        if response.status_code == 200:
            break  # Success, exit the loop
        time.sleep(60)
        attempt += 1
    if response.status_code == 200:
        data = response.json()
        battery_level = data['energy'][0]['level']
        needed_charge = 100 - int(battery_level)
        charge_hours = round((45*(needed_charge/100))/((charging_current*3*225)/1000))
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' INFO: Charge time calculated to be '+str(charge_hours)+' hours.')
        return charge_hours
    else:
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' ERROR: Vehicle info could not be retrieved after '+str(max_attempts)+' attempts. 60 seconds between attempts.')


def charge_start_time(charge_hours, start_time):
    charge_hours += 1
    # Calculate the current and next day
    current_date = datetime.date.today()
    next_date = current_date + datetime.timedelta(days=1)
    # Create the time range string
    time_range = f"{current_date.isoformat()}T22:00_{next_date.isoformat()}T07:00"
    url = 'https://www.sahkohinta-api.fi/api/v1/halpa'
    params = {
        'tunnit': charge_hours,
        'tulos': 'sarja',
        'aikaraja': time_range
    }
    max_attempts = 5
    attempt = 1
    response = None
    while attempt <= max_attempts:
        response = requests.get(url, params=params)
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' INFO: Request URL:', response.request.url)
        print(current_time,' INFO: Response Status Code:', response.status_code)
        if response.status_code == 200:
            break  # Success, exit the loop
        time.sleep(60)
        attempt += 1
    if response.status_code == 200:
        data = response.json()
        # Extract the timestamp and convert it to datetime object
        timestamp = [datetime.datetime.fromisoformat(entry['aikaleima_suomi']) for entry in data]
        # Find the earliest timestamp
        time = min(timestamp).strftime("%H:%M")
        # Update start_time with new value
        start_time = time
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time, ' INFO: Start time updated to '+ start_time +' based on electricity prices.')
        return start_time
    else: # If prices cannot be updated start time is at 02:00.
        start_time = '02:00'
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time," ERROR: Electricity prices couldn't be updated after "+str(max_attempts)+" attempts. 60 seconds between attempts'. Maybe www.sahkonhpinta-api.fi is down. Start time is set to: " + start_time)


def set_charging_start(start_time,vin):
    # example request: http://localhost:5000/charge_hour?vin=YOURVIN&hour=22&minute=30
    hour, minute = start_time.split(':')
    url = 'http://'+baseurl+':5000/charge_hour'
    params = {
        'vin': vin,
        'hour': hour,
        'minute': minute
    }
    max_attempts = 5
    attempt = 1
    response1 = None
    while attempt <= max_attempts:
        response1 = requests.get(url, params=params)
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' INFO: Request URL:', response1.request.url)
        print(current_time,' INFO: Response Status Code:', response1.status_code)
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' INFO: Waiting 30 seconds.')
        time.sleep(30)
        response2 = requests.get('http://'+baseurl+':5000/get_vehicleinfo/'+vin)
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' INFO: Request URL:', response2.request.url)
        print(current_time,' INFO: Response Status Code:', response2.status_code)
        data = response2.json()
        time1 = data['energy'][0]['charging']['next_delayed_time']
        time2 = start_time
        if response1.status_code == 200 and response2.status_code == 200 and convert_to_minutes(time1) == convert_to_minutes(time2):      
            break  # Success, exit the loop
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' ERROR: Time could not be set on attempt number '+str(attempt)+'/'+str(max_attempts)+'. Waiting 15 minutes and trying again.')
        time.sleep(300)
        attempt += 1
    if attempt > max_attempts:
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' ERROR: Start time for charging could not be set after '+str(max_attempts)+' attempts. 15 minutes between each attempt.')
    else:
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time, ' INFO: Start time successfully set. Charging starts at '+start_time)
    

def execute_all(start_time):
    charge_hours = check_needed_charge_time(baseurl, vin, charging_current)
    start_time = charge_start_time(charge_hours, start_time)
    set_charging_start(start_time,vin)
    

# Schedule tasks
schedule.every().day.at(set_time, 'Europe/Helsinki').do(execute_all, start_time).tag('execute_all')

print('Program started. Waiting for scheduled tasks.')
# Main loop to execute scheduled tasks
while True:
    schedule.run_pending()
    time.sleep(1)
