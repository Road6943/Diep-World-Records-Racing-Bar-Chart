# I can't get the mobile stuff to work, so I'm only doing desktop records

# if you want to try fixing it later, then read this to understand what the isDesktop thing does:
# https://github.com/Moeplhausen/dieprecords/blob/d36b6ef370f6d536c6fb21a563659998bb631795/app/Http/Controllers/RecordsController.php#L152

# if True, will make api calls to gather up-to-date data, overwrite records_histories.json, and then make the csv's
# if False, will make csv's from the previously fetched data in record_histories.json
FETCH_NEW_DATA = False

# https://github.com/Moeplhausen/dieprecords/blob/master/routes/api.php
BASE_URL = "http://wra.spade-squad.com"

# the three types of race chart makers are here:
# https://www.ilovefreesoftware.com/18/featured/free-bar-chart-race-generator-tools.html
JSON_OUTPUT_FILE = "record_histories.json" 
FLOURISH_CSV_OUTPUT_FILE = "flourish_record_histories.csv"
FABDEV_CSV_OUTPUT_FILE = "fabdev_record_histories.csv"


import requests
import json
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta


def get_record_histories(tanks, gamemodes):
    """
        in:
            tanks = [ { id:<int>, tankname:<str> } ]
            gamemodes = [ { id:<int>, name:<str>, mobile:<str === "0" or "1"> } ]
        out:
            recordHistories = 
                {
                    @each $tank in $tanks: {
                        "desktop": {
                            @each $gamemode in $gamemodes: {
                                "tankhistory": {
                                "input": {
                                    "tankid": "numberString",
                                    "gamemodeid": "numberString",
                                    "desktop": "0" | "1",
                                },
                                "data": [],
                                "test": 0,
                                }, 
                            }
                        },
                        "mobile": # SAME AS "desktop" # currently not being used because I can't get it to work
                    }
                }
    """
    record_histories = { "desktop": defaultdict(dict), "mobile": defaultdict(dict) }

    for tank in tanks:
        for gamemode in gamemodes:
            # more info on is_desktop:
            # https://github.com/Moeplhausen/dieprecords/blob/d36b6ef370f6d536c6fb21a563659998bb631795/app/Http/Controllers/RecordsController.php#L152
            is_desktop = (gamemode["mobile"] == "0")
            api_url = f"{BASE_URL}/api/history/{ tank['id'] }/{ gamemode['id'] }/{ int(is_desktop) }"
            
            if is_desktop:
                history = requests.get(api_url).json()
                record_histories["desktop"][ tank["tankname"] ][ gamemode["name"] ] = history
            else:
                # skip the mobile gamemodes for now
                pass
        
        #break # comment this out when you want to get every single tank's data

    return record_histories


def organize_data_by_date(record_histories):
    """
        in:
            record_histories
        out:
            records_by_date_list: list of individual record dicts, sorted by their created_at value
            records_by_date_dict: dict mapping date => dict mapping (tank, gamemode) => record dict
    """
    # only accounting for desktop currently
    
    # make a list containing every record dict, sorted by date earliest to latest
    records_by_date_list = []
    for tankname in record_histories["desktop"]:
        for gamemodename in record_histories["desktop"][tankname]:
            new_record = record_histories["desktop"][tankname][gamemodename]["tankhistory"]["data"]
            records_by_date_list.extend(new_record)
    
    def get_timestamp(record) -> float:
        return datetime.strptime(record["created_at"], "%Y-%m-%d %H:%M:%S").timestamp()

    records_by_date_list.sort(key=get_timestamp)

    # There is one battleship score on 2016-10-01
    # Every other tank only shows up on 2016-10-29
    # I'm assuming the latter date is when the wra website actually started being used
    #  and the battleship score was more for testing purposes, so I'm changing its date
    # to 2016-10-29 to make the data more consistent
    records_by_date_list[0]["created_at"] = "2016-10-29 16:07:49"

    # now make the dict, that keys date to the records done on that date
    # key is Y-m-d, no time and val is dict where keys are "tank gamemode"
    #   and those keys are mapped to the actual record dicts
    records_by_date_dict = defaultdict(dict)
    for record in records_by_date_list:
        date = record["created_at"].split()[0]
        
        records_by_date_dict[date][ (record["tank"], record["gamemode"]) ] = record

    return records_by_date_list, records_by_date_dict

        
def format_data_for_flourish(records_by_date_list, records_by_date_dict, tanks, gamemodes):
    """
        in:
            records_by_date_list: list of individual record dicts, sorted by their created_at value
            records_by_date_dict: dict mapping date => dict mapping (tank, gamemode) => record dict
            tanks: list of tank dicts
            gamemodes: list of gamemode dicts
        out:
            list of lists, formatted in the correct format needed for flourish studio to create a racing chart
                each row will belong to a "tankname + gamemodename" combo, like "Spike 4TDM", 
                and that is what will appear in the racing chart
            
            each list inside the bigger list looks as follows:
            ["Record", ...dateStrings]
            ["tank gamemode", ...int scores on the date in first row at same index]
    """
    # only accounting for desktop currently

    tanknames = [ tank["tankname"] for tank in tanks ]

    def is_desktop_gamemode(gamemode):
        return gamemode["mobile"] == "0"

    gamemodenames = [ 
        gamemode["name"] 
        for gamemode in gamemodes 
        if is_desktop_gamemode(gamemode)
    ]

    # make a list of date strings, without times
    # 1 dayStr for each day between earliest and latest dates in the records data, inclusively

    # if given a date like "2020-1-25", returns "2020-1-26"
    def get_next_date(dateStr):
        today = datetime.fromisoformat(dateStr)
        tomorrow = today + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
    
    starting_date = records_by_date_list[0]["created_at"].split()[0]
    ending_date = datetime.today().strftime("%Y-%m-%d")

    dates = []
    d = starting_date
    while d != get_next_date(ending_date):
        dates.append(d)
        d = get_next_date(d)


    # start actually making the formatted data
    # first column is the "Record" col, where the Tank Gamemode descriptor goes, 
    # 2nd col is tank, 3rd col is gamemode, everything after is dates
    formatted_data = []
    formatted_data.append(["Record", "Tank", "Gamemode",  *dates])

    # keep track of the most recently seen score for a record, defaults to 0
    # maps (tank, gamemode) => score number
    last_known_score = defaultdict(int)

    for tankname in tanknames:
        for gamemodename in gamemodenames:
            # start new_row with a description of the record being added
            new_row = [ f"{tankname} {gamemodename}", tankname, gamemodename ]

            for day in dates:
                
                if day in records_by_date_dict:
                    # if tank,gamemode tuple present for data on date, then append it and update last_known_score
                    if (tankname, gamemodename) in records_by_date_dict[day]:
                        score = int( records_by_date_dict[day][(tankname,gamemodename)]["score"] )
                        new_row.append(score)
                        last_known_score[(tankname,gamemodename)] = score
                    
                    # if tank gamemode not in data for that day (no submissions for this tuple on that day)
                    # then just use the last_known score
                    else:
                        new_row.append(
                            last_known_score[(tankname,gamemodename)]
                        )
                
                # if day is not in the records_by_date dict, then just use the previously seen value
                # this means that there were no records submitted on that day
                else:
                    new_row.append( 
                        last_known_score[(tankname, gamemodename)] 
                    )

            # add new row into accumulator matrix
            formatted_data.append(new_row)
    
    return formatted_data


def format_data_for_fabdev(flourish_formatted_data):
    """
        in:
            2d list, formatted for flourish.studio
        out:
            2d list, formatted for https://fabdevgit.github.io/barchartrace/
            click link to learn more
    """
    # this literally just flips the data on its side (flourish wants dates on top row, fabdev wants dates on left column)
    return zip(*flourish_formatted_data)


def print_to_csv(formatted_data, csv_output_file):
    """
        in:
            formatted_data: 2d list
            csv_output_file: filename as string
        out:
            None, it just prints the formatted_data to the csv_output_file
    """
    with open(csv_output_file, "w") as file:
        writer = csv.writer(file)
        writer.writerows(formatted_data)


def main():
    tanks = requests.get( f"{BASE_URL}/api/tanks" ).json()
    gamemodes = requests.get( f"{BASE_URL}/api/gamemodes" ).json()

    record_histories = None
    if FETCH_NEW_DATA:
        record_histories = get_record_histories(tanks, gamemodes)
    else:    
        with open(JSON_OUTPUT_FILE) as f:
            record_histories = json.load(f)

    records_by_date_list, records_by_date_dict = organize_data_by_date(record_histories)

    flourish_formatted_data = format_data_for_flourish(records_by_date_list, records_by_date_dict, tanks, gamemodes)
    print_to_csv(flourish_formatted_data, FLOURISH_CSV_OUTPUT_FILE)

    fabdev_formatted_data = format_data_for_fabdev(flourish_formatted_data)
    print_to_csv(fabdev_formatted_data, FABDEV_CSV_OUTPUT_FILE)


if __name__ == "__main__":
    main()
