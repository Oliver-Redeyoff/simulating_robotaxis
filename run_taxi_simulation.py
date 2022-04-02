from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import time
from typing import List, Tuple
from tqdm import tqdm
import random
import xml.etree.ElementTree as ET

from datatypes import trip, simulation
from utilities import create_dir, retrieve, indent, generate_config

# we need to import python modules from the $SUMO_HOME/tools directory
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

from sumolib import checkBinary
import traci


def generate_trips_file(trips: List[trip], drivable_edges: List[str], simulation_: simulation):

    taxi_routes_root = ET.Element("routes")
    ET.SubElement(taxi_routes_root, 'route', {
        'id': 'route_0',
        'edges': random.choice(list(drivable_edges))
    })
    taxi_def = ET.SubElement(taxi_routes_root, 'vType', {
        'id': 'taxi',
        'vClass': 'taxi'
    })
    ET.SubElement(taxi_def, 'param', {
        'key': 'has.taxi.device',
        'value': 'true'
    })

    taxi_count = 100

    for taxi_id in range(taxi_count):
        taxi_vehicle = ET.SubElement(taxi_routes_root, 'vehicle', {
            'id': 'v'+str(taxi_id), 
            'depart': str(simulation_.start_time*3600) + '.00',
            'type': 'taxi',
            'line': 'taxi'
        })
        ET.SubElement(taxi_vehicle, 'route', {
            'edges': random.choice(list(drivable_edges))
        })

    person_id = 0
    for trip_ in tqdm(trips):
        taxi_vehicle = ET.SubElement(taxi_routes_root, 'person', {
            'id': 'p'+str(person_id), 
            'depart': str(trip_.depart),
            'color': 'green'
        })
        ET.SubElement(taxi_vehicle, 'ride', {
            'from': trip_.from_,
            'to': trip_.to,
            'lines': 'taxi'
        })
        person_id += 1

    taxi_routes_tree = ET.ElementTree(taxi_routes_root)
    indent(taxi_routes_root)
    taxi_routes_tree.write('./temp/'+simulation_.taxi_routes_file, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":

    trips = retrieve('./temp/trips.pkl')
    drivable_edges = retrieve('./temp/drivable_edges.pkl')
    simulation_ = retrieve('./temp/simulation.pkl')

    generate_trips_file(trips, drivable_edges, simulation_)

    create_dir('./out')
    generate_config(simulation_.net_file, simulation_.base_routes_file, simulation_.start_time, simulation_.end_time, './temp/taxi.sumocfg')
    sumoBinary = checkBinary('sumo')
    traci.start([sumoBinary, "-c", './temp/taxi.sumocfg'])

    # print("Adding taxis")
    # taxi_count = 100
    # for taxi_id in range(taxi_count):
    #     traci.vehicle.add(f'taxi{taxi_id}', 'route_0', 'taxi', depart=str(simulation_.start_time), line='taxi')

    while True:
        traci.simulationStep()
        fleet = traci.vehicle.getTaxiFleet(0)
        print("Idle taxis : " + str(fleet))
        print("Busy taxis : " + str(traci.vehicle.getTaxiFleet(2)))
        reservations = traci.person.getTaxiReservations(0)
        reservation_ids = [r.id for r in reservations]
        print("Reservations : " + str(reservation_ids))
        if (len(fleet) and len(reservation_ids) > 0):
            traci.vehicle.dispatchTaxi(fleet[0], reservation_ids[0])
            print('dispatched taxi {} for reservation {}'.format(fleet[0], reservation_ids[0]))
        print()
        time.sleep(1)