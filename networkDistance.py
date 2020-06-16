'''
module networkDistance
Author: David James, 20200616, davidabraham@ucla.edu
functions:
    - mp_findDrivingDistance
    - mp_networkDriver
'''
import logging as lg
import multiprocessing as mp

import requests
import pandas as pd
import numpy as np
import datetime as dt

def mp_networkDriver(data, locs, name):
    """Runs the OSRM software collecting the results from the server.

    Parameters
    ----------
    data : DataFrame
        A two column pandas.DataFrame of ints containing the geocodes of
        the source and destination.
    locs : Dictionary
        A Dictionary with string keys connected to DataFrames. Each key is
        a two digit state FIPS code and the DataFrame is a three column of
        string FIPS geocodes along with its associated latitude and longitude
        represented as floats
    name : str
        Name of the file being provided. This will be used for the output
        files to show which result files are associated with.

    Returns
    -------
    None

    Notes
    -----
    The order of the source and destination in the data parameter does not
    matter. However, the locs parameter must have its keys as 2-digit strings
    with its value DataFrames ordered in
    (GEOCODES(str), LAT(float), LON(float)). Otherwise, the OSRM will crash
    or parse your calls incorrectly.
    """

    lg.basicConfig(format='%(asctime)s %(message)s')

    # getting the number of cpu cores on computer
    cores = mp.cpu_count()

    # when running tests change rows to a smaller fixed value
    rows = data.shape[0]
    group = rows//cores

    mpCount = [(group*i, group*(i+1), data, locs, name) if i < cores-1
               else (group*i, rows, data, locs, name)
               for i in range(cores)]

    # creating threads to run
    pool = mp.Pool(cores)

    lg.info('Started processing')

    # processing distances
    pool.map(mp_findDrivingDistance,mpCount)

    lg.info('Finished processing')
    pool.close()

def meters_to_miles(meters):
    """Converts the input value of meters into miles.

    """
    miles = meters / 1609.344
    return miles

def mp_findDrivingDistance(index):
    """Makes calls to the OSRM server to calculate the network distance.

    Parameters
    ----------
    index : tuple
        The starting and ending index of the data set.

    Returns
    -------
    None

    Notes
    -----
    At the end, this function will save two files of the computed geocode
    pars and the missed values.
    """
    keys = ['Home Block', 'Home Lat', 'Home Lon',
            'Work Block', 'Work Lat', 'Work Lon',
            'Distance [mi]']
    commutes = {keys[0]:[], keys[1]:[], keys[2]:[],
                keys[3]:[], keys[4]:[], keys[5]:[],
                keys[6]:[]}
    missedBlocks = {keys[0]:[], keys[3]:[]}
    worker = mp.current_process()
    wid = worker.name

    data = index[2]
    datakeys = data.keys()
    locs = index[3]
    name = index[4]

    for i in range(index[0],index[1]):
        # getting the FIPS code for home and work blocks
        work = data[datakeys[0]][i]
        home = data[datakeys[1]][i]

        # retrieving state FIPS code
        wState = work[:2]
        hState = home[:2]

        # gathering column names from locs DataFrame
        lockeys = locs[wState].keys()
        geo = lockeys[0]
        lat = lockeys[1]
        lon = lockeys[2]

        # get lat,lon from current county
        wLatLon = locs[wState][work == locs[wState][geo]].reset_index(drop=True)
        hLatLon = locs[hState][home == locs[hState][geo]].reset_index(drop=True)

        # place retrieved lat,lon into url for server
        # NOTE: server takes location in lon,lat format
        try:
            # parsing lat,lon values
            homeLat = hLatLon[lat][0]
            homeLon = hLatLon[lon][0]
            workLat = wLatLon[lat][0]
            workLon = wLatLon[lon][0]

            # generating url to call server
            url = ('http://127.0.0.1:5000/route/v1/driving/{0},{1};{2},{3}?steps=true'
                   .format(homeLon,
                           homeLat,
                           workLon,
                           workLat))

            # calling server
            response = requests.get(url).json()
            # retrieving distance and converting to miles
            distance = response['routes'][0]['distance']
            distance = meters_to_miles(distance)

            # appending all necessary values to dictionary
            commutes[keys[0]].append(home)
            commutes[keys[1]].append(homeLat)
            commutes[keys[2]].append(homeLon)
            commutes[keys[3]].append(work)
            commutes[keys[4]].append(workLat)
            commutes[keys[5]].append(workLon)
            commutes[keys[6]].append(distance)
        except:
            # any missed values get appened to other dictionary
            missedBlocks[keys[0]].append(home)
            missedBlocks[keys[3]].append(work)

    lg.info('index ' + str(index[0]) + ','+ str(index[1]) + ' done processing: ' + str(wid))

    # time stamp for file name
    now = dt.datetime.now().strftime("%Y%m%d-%H%M")
    # saving files
    title = now + '-' + name + '-' + wid + '.csv'
    miss = pd.DataFrame(missedBlocks).to_csv('missed/' + title, index=False)
    hits = pd.DataFrame(commutes).to_csv('results/'+ title, index=False)
