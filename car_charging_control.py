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



# Set the time zone to Finnish time (Eastern European Time) for datetime
finnish_tz = pytz.timezone('Europe/Helsinki')

vin = 'YOURVIN'
set_time = '20:00'
charge_time = 7 # charge time in hours
start_time = '02:00'
charging_current = 13 # Charging current per phase in A
baseurl = 'localhost' # IP for the psa-car-control


def check_needed_charge_time(baseurl, vin, charging_current):
    max_attempts = 5
    attempt = 1
    response = None
    while attempt <= max_attempts:
        response = requests.get('http://'+baseurl+':5000/get_vehicleinfo/'+vin)
        if response.status_code == 200:
            break  # Success, exit the loop
        time.sleep(60)
        attempt += 1
    if response.status_code == 200:
        data = response.json()
        battery_level = data['energy']['0']['level']
        needed_charge = 100 - int(battery_level)
        charge_time = round((45*(needed_charge/100))/((charging_current*3*225)/1000))
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' INF: Charge time calculated to be '+str(charge_time)+' hours.')
        return charge_time
    else:
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' ERR: Vehicle info could not be retrieved after '+max_attempts+' attempts. 60 seconds between attempts.')


def charge_start_time(charge_time, start_time):
    charge_time += 1
    # Calculate the current and next day
    current_date = datetime.date.today()
    next_date = current_date + datetime.timedelta(days=1)
    # Create the time range string
    time_range = f"{current_date.isoformat()}T22:00_{next_date.isoformat()}T07:00"
    url = 'https://www.sahkohinta-api.fi/api/v1/halpa'
    params = {
        'tunnit': charge_time,
        'tulos': 'sarja',
        'aikaraja': time_range
    }
    max_attempts = 5
    attempt = 1
    response = None
    while attempt <= max_attempts:
        response = requests.get(url, params=params)
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
        print(current_time, ' INF: Start time updated to '+ start_time +' based on electricity prices.')
        return start_time
    else: # If prices cannot be updated start time is at 02:00.
        start_time = '02:00'
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time," ERR: Electricity prices couldn't be updated after "+max_attempts+" attempts. 60 seconds between attempts'. Maybe www.sahkonhpinta-api.fi is down. Start time is set to: " + start_time)


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
    response = None
    while attempt <= max_attempts:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            break  # Success, exit the loop
        time.sleep(60)
        attempt += 1
    if response.status_code == 200:
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time, ' INF: Start time for charging set to: '+start_time+' successfully.')
    else:
        current_time = datetime.datetime.now(finnish_tz).time()
        print(current_time,' ERR: Start time for charging could not be set after '+max_attempts+' attempts. 60 seconds between attempts.')
    

def execute_all():
    charge_time = check_needed_charge_time(baseurl, vin, charging_current)
    start_time = charge_start_time(charge_time, start_time)
    set_charging_start(start_time,vin)
    

# Schedule tasks
schedule.every().day.at(set_time, 'Europe/Helsinki').do(execute_all).tag('execute_all')

# Main loop to execute scheduled tasks
while True:
    schedule.run_pending()
    time.sleep(1)
