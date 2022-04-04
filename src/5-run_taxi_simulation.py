from __future__ import absolute_import
from __future__ import print_function
from functools import total_ordering

import os
import sys
import time
from typing import List
from tqdm import tqdm
import random
import xml.etree.ElementTree as ET

from datatypes import trip, simulation, taxi_states, reservation_states
from utilities import create_dir, retrieve, indent, generate_config

# we need to import python modules from the $SUMO_HOME/tools directory
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
    from sumolib import checkBinary
    import traci
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")


def generate_trips_file(trips: List[trip], drivable_edges: List[str], simulation_: simulation, taxi_count: int):

    taxi_routes_root = ET.Element("routes")

    taxi_def = ET.SubElement(taxi_routes_root, 'vType', {
        'id': 'taxi',
        'vClass': 'taxi',
        'personCapacity': '8'
    })
    ET.SubElement(taxi_def, 'param', {
        'key': 'has.taxi.device',
        'value': 'true'
    })

    for taxi_id in range(taxi_count):
        ET.SubElement(taxi_routes_root, 'route', {
            'edges': random.choice(list(drivable_edges)),
            'id': 'route'+str(taxi_id)
        })
        taxi_vehicle = ET.SubElement(taxi_routes_root, 'vehicle', {
            'id': 'v'+str(taxi_id), 
            'depart': str(simulation_.start_time) + '.00',
            'type': 'taxi',
            'line': 'taxi',
            'route': 'route'+str(taxi_id)
        })
        # ET.SubElement(taxi_vehicle, 'route', {
        #     'edges': random.choice(list(drivable_edges))
        # })

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
    taxi_routes_tree.write('../temp/' + simulation_.taxi_routes_file, encoding="utf-8", xml_declaration=True)

def dispatch_to_reservation(reservation, idle_taxi_ids):
    for taxi_id in idle_taxi_ids:
        taxi_edge_id = traci.vehicle.getRoadID(taxi_id)
        pickup_edge_id = reservation.fromEdge

        route = traci.simulation.findRoute(taxi_edge_id, pickup_edge_id, vType='taxi')
        
        if (route.length != 0):
            print('dispatched taxi {} on edge {} for reservation {} on edge {}'.format(taxi_id, taxi_edge_id, reservation.id, pickup_edge_id))
            dropoff_route = traci.simulation.findRoute(reservation.fromEdge, reservation.toEdge, vType='taxi')
            if (dropoff_route.length == 0):
                print('there is no way to get to the dropoff though!!')
            traci.vehicle.dispatchTaxi(taxi_id, reservation.id)
            return taxi_id
        break
    return None

if __name__ == "__main__":

    trips: List[trip] = retrieve('../temp/trips.pkl')
    drivable_edges = retrieve('../temp/drivable_edges.pkl')
    simulation_: simulation = retrieve('../temp/simulation.pkl')

    generate_trips_file(trips, drivable_edges, simulation_, 100)

    create_dir('../out')
    generate_config(simulation_.net_file, simulation_.taxi_routes_file, simulation_.start_time, simulation_.end_time, '../temp/taxi.sumocfg')
    sumoBinary = checkBinary('sumo')
    traci.start([sumoBinary, "-c", '../temp/taxi.sumocfg'])

    # print("Adding taxis")
    # for taxi_id in range(taxi_count):
    #     traci.vehicle.add(f'taxi{taxi_id}', 'route_'+str(taxi_id), 'taxi', depart=str(simulation_.start_time), line='taxi')

    # Loop for orchestrating taxis
    total_reservations = 0
    total_dispatches = 0
    for _ in tqdm(range(simulation_.start_time, simulation_.end_time)):

        # Move to next simulation step
        traci.simulationStep()
        # print(traci.simulation.getTime())
        if (traci.simulation.getTime()%1000 == 0):
            print("Total reservations: {} and total dispatches: {}".format(total_reservations, total_dispatches))
            print(len(list(traci.vehicle.getTaxiFleet(taxi_states.any_state.value))))

        # Get list of idle taxis and reservations
        idle_taxi_ids = list(traci.vehicle.getTaxiFleet(taxi_states.empty.value))
        new_reservations = list(traci.person.getTaxiReservations(reservation_states.new.value))
        total_reservations += len(new_reservations)

        for reservation in new_reservations:
            dispatched_taxi_id = dispatch_to_reservation(reservation, idle_taxi_ids)
            if (dispatched_taxi_id != None):
                idle_taxi_ids.remove(dispatched_taxi_id)
                total_dispatches += 1
        