'''
module networkDistance
Author: David James, 20200116, davidabraham@ucla.edu
functions:
    - mp_openCounty
    - mp_findDrivingDistance
    - mp_networkDriver
'''
import requests
import pandas as pd
import numpy as np
import multiprocessing as mp
import datetime as dt

# date/time stamp for saving files
now = dt.datetime.now().strftime("%Y%m%d-%H%M")
geo = 'GEOID10'
lat = 'INTPTLAT10'
lon = 'INTPTLON10'

'''
function mp_openCounty
A function designed to work with multiprocessing
where each worker opens .csv file as a
DataFrame to be allocated to a dictionary
@param: tuple(
        index[0] - int,starting index
        index[1] - int,ending index)
@return: dictionary(
        key: str,county - name of county
        value: DataFrame(
            Series,GEOID10 - int,FIPS code of block
            Series,INTPTLAT10 - float,Latitude of block
            Series,INTPTLON10 - float,Longitude of block))
'''
def mp_openCounty(index):
    blockCounties = {}
    for i in range(index[0],index[1]):
        county = countyWUni[i]
        df = pd.read_csv('countiesCSV/'+county+'.csv',
                         usecols=[geo,lat,lon],
                         dtype={geo:np.int64,
                                lat:np.float64,
                                lon:np.float64})
        blockCounties[county] = df
    print('done opening')
    return blockCounties

'''
function mp_findDrivingDistance
A function designed to work with multiprocessing
where each worker will calculate the driving distance
between the home block and the work block
@param: tuple(
        int,index[0] - starting index
        int,index[1] - ending index)
@return: DataFrame(
            Series, Home Block - int, FIPS code of home location
            Series, Home Lat - float, latitude of home
            Series, Home Lon - float, longitude of home
            Series, Work Block - int, FIPS code of work location
            Series, Work Lat - float, latitude of work
            Series, Work Lon - float, longitude of work
            Series, Distance [m] - float, commuting distance between
                                        home and work locations)
'''
def mp_findDrivingDistance(index):
    commutes = {'Home Block':[],'Home Lat':[],'Home Lon':[],
                 'Work Block':[],'Work Lat':[],'Work Lon':[],
                 'Distance [m]':[]}
    missedBlocks = {'Home Block':[], 'Work Block':[]}
    worker = mp.current_process()
    wid = worker.name

    for i in range(index[0],index[1]):
        # getting the FIPS code for home and work blocks
        homeBlock = home[i]
        workBlock = work[i]

        # check what county homeBlock is in
        countyHomeBlock = str(homeBlock)[1:4]
        countyWorkBlock = str(workBlock)[1:4]
        # find county within dictionary of geoIDs,lats and lon points
        homeCounty = blockCounties[countyHomeBlock]
        workCounty = blockCounties[countyWorkBlock]

        # get lat,lon from current county
        homeLatLon = homeCounty[homeBlock == homeCounty[geo]].reset_index(drop=True)
        workLatLon = workCounty[workBlock == workCounty[geo]].reset_index(drop=True)

        # place retrieved lat,lon into url for server
        # NOTE: server takes location in lon,lat format
        try:
            homeLat = homeLatLon[lat][0]
            homeLon = homeLatLon[lon][0]
            workLat = workLatLon[lat][0]
            workLon = workLatLon[lon][0]
            url = ('http://127.0.0.1:5000/route/v1/driving/{0},{1};{2},{3}?steps=true'
                   .format(homeLon,
                           homeLat,
                           workLon,
                           workLat))
            response = requests.get(url).json()
            distance = response['routes'][0]['distance']
            # appending all necessary values
            commutes['Home Block'].append(homeBlock)
            commutes['Home Lat'].append(homeLat)
            commutes['Home Lon'].append(homeLon)
            commutes['Work Block'].append(workBlock)
            commutes['Work Lat'].append(workLat)
            commutes['Work Lon'].append(workLon)
            commutes['Distance [m]'].append(distance)
        except:
            missedBlocks['Home Block'].append(homeBlock)
            missedBlocks['Work Block'].append(workBlock)

    nowTime = dt.datetime.now().strftime("%H%M")
    now = dt.datetime.now().strftime("%Y%m%d-%H%M")
    print('index',index,'done processing', nowTime, wid)
    miss = pd.DataFrame(missedBlocks).to_csv('results/missedBlocks'+ now + '-' + wid + '.csv')
    hits = pd.DataFrame(commutes).to_csv('results/commutes'+ now + '-' + wid + '.csv')

'''
function mp_networkDriver
A function designed to work with multiprocessing
where it'll run the previous designed functions
NOTE: This will crash if the docker OSRM isn't running beforehand
@param:
             path - str, path to CSV file that will be prococcsed
    startGeoIDCol - str, name of column that has the starting GEOIDs
      endGeoIDCol - str, name of column that has the ending GEOIDs
@return: NONE
'''
def mp_networkDriver(path,startGeoIDCol,endGeoIDCol):
    # pulling commuter data from California csv
    area = pd.read_csv(path,
                       usecols=[startGeoIDCol,endGeoIDCol])

    # creating 2 Series of the startGeoIDCol and endGeoIDCol columns
    work = area[startGeoIDCol]
    home = area[endGeoIDCol]

    # creating a Series of the unique county FIPS values within the startGeoIDCols column
    countyWork = [str(x)[1:4] for x in work]
    countyWork = pd.Series(countyWork)
    countyWUni = countyWork.unique()
    blockCounties = {}

    # getting the number of cpu cores on computer
    cores = mp.cpu_count()

    # creating indexs to separate jobs for each thread
    # Note:
    # indexes are based on if running on 4 cores
    processOpenCounties = [(0,14),(14,28),(28,42),(42,58)]
    rows = cali.shape[0]
    group = rows//cores
    a0 = 0
    a1 = group * 1
    a2 = group * 2
    a3 = group * 3
    a4 = rows
    processCountiesIndex = [(a0,a1),(a1,a2),(a2,a3),(a3,a4)]

    # creating threads to run
    pool = mp.Pool(cores)

    # opening necessary csv files to process
    results = pool.map(mp_openCounty,processOpenCounties)
    # combining the dictionaries from multiple workers into one dictionary
    for d in results:
        blockCounties.update(d)

    pool.close()

    # creating threads to run
    pool = mp.Pool(cores)

    nowTime = dt.datetime.now().strftime("%H%M")
    print('Starting processing at', nowTime)

    # processing distances
    pool.map(mp_findDrivingDistance,processCountiesIndex)

    nowTime = dt.datetime.now().strftime("%H%M")
    print('Finished processing at', nowTime)

    pool.close()
