from typing import List
import math
import random
import os
import sys

import xml.etree.ElementTree as ET
from tqdm import tqdm

from datatypes import trip, TripInfo
from utilities import retrieve

def run():

    trips: List[trip] = retrieve('../temp/trips.pkl')
    trip_ids = [str(trip_.id) for trip_ in trips]

    # Retrive tripinfos for both simulations
    base_info_tree = ET.parse('../out/base.tripinfo.xml')
    base_info_root = base_info_tree.getroot()
    base_trip_infos: List[TripInfo] = {}

    taxi_info_tree = ET.parse('../out/taxi.tripinfo.xml')
    taxi_info_root = taxi_info_tree.getroot()
    taxi_trip_infos: List[TripInfo] = {}

    for trip_info in base_info_root.findall('tripinfo'):
        base_trip_infos[trip_info.attrib['id']] = TripInfo(
            trip_info.attrib['id'],
            '',
            0.0,
            float(trip_info.attrib['duration']),
            float(trip_info.attrib['routeLength'])
        )

    for trip_info in taxi_info_root.findall('personinfo'):
        ride_info = trip_info[0]
        taxi_trip_infos[trip_info.attrib['id']] = TripInfo(
            trip_info.attrib['id'],
            ride_info.attrib['vehicle'],
            float(ride_info.attrib['waitingTime']),
            float(ride_info.attrib['duration']),
            float(ride_info.attrib['routeLength'])
        )

    base_total_travel_time = 0
    taxi_total_travel_time = 0
    for trip_id in trip_ids:
        if (trip_id in base_trip_infos and trip_id in taxi_trip_infos):
            base_total_travel_time += base_trip_infos[trip_id].duration
            taxi_total_travel_time += taxi_trip_infos[trip_id].duration

    print('base travel time: {}, taxi travel time: {}'.format(base_total_travel_time, taxi_total_travel_time))
    print('taxi travel times is {}% off the duration of base travel times'.format(taxi_total_travel_time/base_total_travel_time*100))

if __name__ == '__main__':
    run()