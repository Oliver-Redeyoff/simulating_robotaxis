from typing import List
import csv
import json
import requests
import os
import sys
import xml.etree.ElementTree as ET
from pyproj import Transformer

import folium
import utm
from shapely.geometry import shape, Point

from datatypes import Count, CountPoint, P, City, Simulation
from utilities import create_dir, store

# We need to import python modules from the $SUMO_HOME/tools directory
if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
    import osmGet
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")


# Add counts to the list of counts for point
def aggregate_counts(count_point: CountPoint, raw_count):

    for count in count_point.counts:
        if (count.hour == int(raw_count[P.hour.value])):
            # add count to average
            count.value_sum += int(raw_count[P.cars_and_taxis.value])
            count.value_count += 1
            return

    count_point.counts.append(Count(
        int(raw_count[P.hour.value]),
        int(raw_count[P.cars_and_taxis.value]),
        1
    ))

def run():

    # Define city to run simulation on
    city = City(
        "Bath",
        0,
        0,
        None,
        None,
        None
    )


    # Get position of city using Google maps places API
    x = requests.get('https://maps.googleapis.com/maps/api/geocode/json?address=' 
                    + city.name + ', UK&key=AIzaSyAhmPLZ2MEGQK1-7rTmyjbN_r6Pnqjr8YM')
    res = json.loads(x.text)

    city.geometry = res['results'][0]['geometry']
    city.bbox = city.geometry['viewport']
    m = folium.Map(
            location=[city.geometry['location']['lat'], 
            city.geometry['location']['lng']]
        )


    # Download OSM data using bounding box of place
    create_dir('../temp')
    status = 504
    attempts = 1
    while (status == 504):
        if (attempts == 10):
            sys.exit('Took too many attempts to download osm data')
        print("Attempt {} to get osm data".format(attempts))
        bbox_str = ' ' + \
            str(city.bbox['southwest']['lng']) + ',' + \
            str(city.bbox['southwest']['lat']) + ',' + \
            str(city.bbox['northeast']['lng']) + ',' + \
            str(city.bbox['northeast']['lat'])
        status = osmGet.get(['--bbox', bbox_str,
                    '--output-dir', '../temp'])
        attempts += 1


    # Figure out which local authority the city is in
    with open('local_authorities.geojson', 'r') as myfile:
        local_authorities_raw = myfile.read()
    local_authorities = json.loads(local_authorities_raw)

    transformer = Transformer.from_crs("epsg:4326", "epsg:3857")
    city.position = Point(
        transformer.transform(
            city.geometry['location']['lat'], 
            city.geometry['location']['lng']
        )
    )

    for local_authority in local_authorities['features']:
        multipolygon = shape(local_authority['geometry'])
        if multipolygon.contains(city.position):
            city.local_authority_id = int(local_authority['properties']['id'])
            print("Found city in " + local_authority['properties']['Name'])

    if (city.local_authority_id == 0):
        sys.exit("Could not find city in any british local authority")

    
    # Retrieve the population of the city
    with open('./city_populations.csv', mode='r') as csv_city_populations:
        csv_reader = csv.DictReader(csv_city_populations)
        for row in csv_reader:
            if (row['city'].lower() == city.name.lower()):
                city.population = int(row['population_proper'])
                print('Population of {} is {}'.format(city.name, city.population))

    if (city.population == 0):
        sys.exit('Could not find population of city')
    else:
        simulation = Simulation(
            city,
            23, 
            0,
            0, 
            0,
            'city.net.xml',
            'base.routes.xml',
            'taxi.routes.xml')
        store(simulation, '../temp/simulation.pkl')

    
    # Get count point data for relevant local authority
    x = requests.get(
        'https://storage.googleapis.com/dft-statistics/road-traffic/downloads/rawcount/local_authority_id/' + \
        'dft_rawcount_local_authority_id_' + str(city.local_authority_id) + '.csv');
    raw_counts = x.text.split('\n');
    raw_counts = list(csv.reader(raw_counts));
    list.pop(raw_counts);
    raw_counts.pop(0);


    # Reduce each count for a point at a certain time of day into one average value
    # Only include counts from 2019 and before
    raw_counts = [point for point in raw_counts if int(point[P.year.value]) <= 2019];

    count_points: List[CountPoint] = []

    # reduce raw counts to average count at each count point
    for raw_count in raw_counts:

        count_point_id = raw_count[P.count_point_id.value];
        
        # need to define count_point if it hasn't been added yet
        if (count_point_id not in [point.id for point in count_points]):
            new_count_point = CountPoint(
                count_point_id,
                raw_count[P.road_name.value],
                float(raw_count[P.latitude.value]),
                float(raw_count[P.longitude.value]),
                utm.from_latlon(
                    float(raw_count[P.latitude.value]), 
                    float(raw_count[P.longitude.value])
                ),
                [],
                (-1, None)
            )
            aggregate_counts(new_count_point, raw_count)
            count_points.append(new_count_point)
        # if count_point has already been defined, add count to it
        else:
            for count_point in count_points:
                if (count_point.id == count_point_id):
                    aggregate_counts(count_point, raw_count)


    # Write data to file
    store(count_points, '../temp/count_points.pkl')

if __name__ == '__main__':
    run()