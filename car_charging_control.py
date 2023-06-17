import datetime
import schedule
import time
import pytz
import requests
import math

# PSA Car Control requests used here:

# 1 Get the car state :
# http://localhost:5000/get_vehicleinfo/YOURVIN

# 2 Change charge hour (for example: set it to 22h30)
# http://localhost:5000/charge_hour?vin=YOURVIN&hour=22&minute=30


vin = 'yourvin' # Car's VIN as a string.
execution_time = '22:30' # When the prices are checked and the start time for the car set.
charge_hours = 5 # default charge time in hours if the needed charge time cannot be calculated.
charging_start_time = '02:00' # default charging start time if there is some problems getting the prices etc.
charging_current = 13 # Charging current per phase in A. Three phases assumed to be used.
charging_efficiency = 80 # Charging efficiency as %.
# Start time of the time range for price checking for the lowest prices. Start time is current day and stop time is the next day. So for example 23:00 - 07:00 over the night.
price_check_time_range_start = '23:00'
price_check_time_range_stop = '07:00'
baseurl = '192.168.0.200' # IP to your psa-car-control listener.
localization = 'Europe/Helsinki'
timezone = pytz.timezone(localization) # Set the time zone to Finnish time (Eastern European Time) for datetime


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


def check_needed_charge_time(baseurl, vin, charging_current, charging_efficiency):
    max_attempts = 5
    attempt = 1
    response = None
    while attempt <= max_attempts:
        response = requests.get('http://'+baseurl+':5000/get_vehicleinfo/'+vin)
        current_time = datetime.datetime.now(timezone).time()
        print(current_time,' INFO: Request URL:', response.request.url)
        print(current_time,' INFO: Response Status Code:', response.status_code)
        if response.status_code == 200:
            break  # Success, exit the loop
        else:
            print(current_time,' ERROR: Vehicle info could not be retrieved on attempt number '+str(attempt)+'/'+str(max_attempts)+'. Waiting 1 minute and trying again.')
            time.sleep(60)
            attempt += 1
    if response.status_code == 200:
        data = response.json()
        battery_level = data['energy'][0]['level']
        needed_charge = 100 - int(battery_level)
        charge_hours = round((45*(needed_charge/100))/((charging_efficiency/100)*(charging_current*3*230)/1000), 2) # Charge hours with two decimal accuracy
        current_time = datetime.datetime.now(timezone).time()
        print(current_time,' INFO: Charge time calculated to be '+str(charge_hours)+' hours.')
        return charge_hours
    else:
        current_time = datetime.datetime.now(timezone).time()
        print(current_time,' ERROR: Vehicle info could not be retrieved after '+str(max_attempts)+' attempts. 1 minute between attempts.')


def calculate_charging_start_time(charge_hours, charging_start_time, price_check_time_range_start, price_check_time_range_stop):
    charge_hours = math.ceil(charge_hours)
    charge_hours += 1
    # Calculate the current and the next day
    current_date = datetime.date.today()
    next_date = current_date + datetime.timedelta(days=1)
    # Create the time range string
    time_range = f'{current_date.isoformat()}T{price_check_time_range_start}_{next_date.isoformat()}T{price_check_time_range_stop}'
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
        current_time = datetime.datetime.now(timezone).time()
        print(current_time,' INFO: Request URL:', response.request.url)
        print(current_time,' INFO: Response Status Code:', response.status_code)
        if response.status_code == 200:
            break  # Success, exit the loop
        else:
            print(current_time,' ERROR: Prices could not be updated on attempt number '+str(attempt)+'/'+str(max_attempts)+'. Waiting 1 minute and trying again.')
            time.sleep(60)
            attempt += 1
    if response.status_code == 200:
        data = response.json()
        # Extract the timestamp and convert it to datetime object
        timestamp = [datetime.datetime.fromisoformat(entry['aikaleima_suomi']) for entry in data]
        # Find the earliest timestamp
        time_min = min(timestamp).strftime("%H:%M")
        # Check if the last hour is cheaper than the first hour and shift the charging_start_time if it is.
        first_price = data[0]["hinta"]
        last_price = data[-1]["hinta"]
        if charge_hours > 1 and first_price >= last_price:
            excess_time = 1 - (charge_hours - int(charge_hours))
            # Parse the time string to a datetime object
            time_obj = datetime.datetime.strptime(time_min, "%H:%M")
            # Add excess_time to the time
            new_time_obj = time_obj + datetime.timedelta(hours=excess_time)
            # Convert the datetime object back to a string in the desired format
            new_time_min = new_time_obj.strftime("%H:%M")
            charging_start_time = new_time_min
        else:
            charging_start_time = time_min
        current_time = datetime.datetime.now(timezone).time()
        print(current_time, ' INFO: Start time updated to '+ charging_start_time +' based on electricity prices.')
        return charging_start_time
    else: # If prices cannot be updated start time is at 02:00.
        current_time = datetime.datetime.now(timezone).time()
        print(current_time," ERROR: Electricity prices couldn't be updated after "+str(max_attempts)+" attempts. 60 seconds between attempts'. Maybe www.sahkonhpinta-api.fi is down. Start time is set to: " + charging_start_time)


def set_charging_start(charging_start_time,vin):
    # example request: http://localhost:5000/charge_hour?vin=YOURVIN&hour=22&minute=30
    hour, minute = charging_start_time.split(':')
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
        current_time = datetime.datetime.now(timezone).time()
        print(current_time,' INFO: Request URL:', response1.request.url)
        print(current_time,' INFO: Response Status Code:', response1.status_code)
        current_time = datetime.datetime.now(timezone).time()
        print(current_time,' INFO: Waiting 30 seconds.')
        time.sleep(30)
        response2 = requests.get('http://'+baseurl+':5000/get_vehicleinfo/'+vin)
        current_time = datetime.datetime.now(timezone).time()
        print(current_time,' INFO: Request URL:', response2.request.url)
        print(current_time,' INFO: Response Status Code:', response2.status_code)
        data = response2.json()
        time1 = data['energy'][0]['charging']['next_delayed_time']
        time2 = charging_start_time
        if response1.status_code == 200 and response2.status_code == 200 and convert_to_minutes(time1) == convert_to_minutes(time2):      
            break  # Success, exit the loop
        current_time = datetime.datetime.now(timezone).time()
        print(current_time,' ERROR: Time could not be set on attempt number '+str(attempt)+'/'+str(max_attempts)+'. Waiting 15 minutes and trying again.')
        time.sleep(300)
        attempt += 1
    if attempt > max_attempts:
        current_time = datetime.datetime.now(timezone).time()
        print(current_time,' ERROR: Start time for charging could not be set after '+str(max_attempts)+' attempts. 15 minutes between each attempt.')
    else:
        time.sleep(2)
        current_time = datetime.datetime.now(timezone).time()
        print(current_time, ' INFO: Start time successfully set. Charging starts at '+charging_start_time)
    

def execute_all(charging_start_time):
    charge_hours = check_needed_charge_time(baseurl, vin, charging_current, charging_efficiency)
    time.sleep(1)
    charging_start_time = calculate_charging_start_time(charge_hours, charging_start_time, price_check_time_range_start, price_check_time_range_stop)
    time.sleep(1)
    set_charging_start(charging_start_time,vin)
    

# Schedule tasks
schedule.every().day.at(execution_time, 'Europe/Helsinki').do(execute_all, charging_start_time).tag('execute_all')

print('Program started. Waiting for scheduled tasks..')
# Main loop to execute scheduled tasks
while True:
    schedule.run_pending()
    time.sleep(1)
