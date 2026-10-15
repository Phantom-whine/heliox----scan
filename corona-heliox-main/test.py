import datetime

def break_time_string(time_string:str) -> dict:
    d, t = time_string.split()

    hour, minute, sec = t.split(':')
    year, month, day = d.split('-')

    date_object = {
        'Date': d,
        'Time': t,
        'Hour': hour,
        'Minute': minute,
        'Second': sec,
        'Year': year,
        'Month': month,
        'Day': day
    }

    return date_object


date = "2025-11-08 16:26:22"

date_obj = datetime.datetime(month=11, day=11, hour=10, minute=26, second=22, year=2025)

time_diff = datetime.datetime.now() - date_obj

# print(time_diff.seconds/60/60)

if time_diff.days > 0 :
    print(f'Time diff = {time_diff.days} days ago')
elif time_diff.seconds/60/60 > 0 :
    time_effect = time_diff.seconds/60/60

    print(f'Time diff = {round(time_effect)} Hours ago')
else :
    time_effect = time_diff.seconds/60

    print(f'Time diff = {round(time_effect)} Minutes ago')