from __future__ import absolute_import
from __future__ import print_function

from dataclasses import dataclass, field
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


@dataclass
class Taxi:
    id: str
    unreachable_reservations_count: int = 0
    pickup: List[str] = field(default_factory=list)

# Instantiate global variables
verbose = False
taxis: List[Taxi] = []
reservations_queue = []


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

def get_available_taxi(reservation, idle_taxis: List[Taxi]):

    global taxis

    for taxi in idle_taxis:
        taxi_edge_id = traci.vehicle.getRoadID(taxi.id)
        pickup_edge_id = reservation.fromEdge

        route = traci.simulation.findRoute(taxi_edge_id, pickup_edge_id, vType='taxi')
        
        if (route.length != 0):
            # print('dispatched taxi {} on edge {} for reservation {} on edge {}'.format(taxi_id, taxi_edge_id, reservation.id, pickup_edge_id))
            # dropoff_route = traci.simulation.findRoute(reservation.fromEdge, reservation.toEdge, vType='taxi')
            # if (dropoff_route.length == 0):
            #     print('there is no way to get to the dropoff though!!')
            return taxi
        else:
            taxi.unreachable_reservations_count += 1
            # Remove taxis which weren't able to reach reservations 10 times
            # as they are probably in some weird spot of the network
            if (taxi.unreachable_reservations_count>10):
                if (verbose):
                    print('Removing taxi ' + taxi.id)
                taxis.remove(taxi)
                idle_taxis.remove(taxi)

    return None

def run():

    global taxis
    taxi_count = 1000
    taxis = [Taxi('v'+str(i)) for i in range(taxi_count)]

    # Retrieve data
    trips: List[trip] = retrieve('../temp/trips.pkl')
    drivable_edges = retrieve('../temp/drivable_edges.pkl')
    simulation_: simulation = retrieve('../temp/simulation.pkl')

    # Generate trips file
    generate_trips_file(trips, drivable_edges, simulation_, taxi_count)

    # Generate sumo config file and start simulation
    create_dir('../out')
    generate_config(simulation_.net_file, simulation_.taxi_routes_file, simulation_.start_time, simulation_.end_time, '../temp/taxi.sumocfg', True)
    sumoBinary = checkBinary('sumo')
    traci.start([sumoBinary, 
                '--configuration-file', '../temp/taxi.sumocfg',
                '--tripinfo-output', '../out/taxi.tripinfo.xml'])

    # print("Adding taxis")
    # for taxi_id in range(taxi_count):
    #     traci.vehicle.add(f'taxi{taxi_id}', 'route_'+str(taxi_id), 'taxi', depart=str(simulation_.start_time), line='taxi')

    # Orchestrate taxis
    total_reservations = 0
    total_dispatches = 0
    for _ in tqdm(range(simulation_.start_time, simulation_.end_time)):

        # Move to next simulation step
        traci.simulationStep()
        # print(traci.simulation.getTime())
        if (traci.simulation.getTime()%100 == 0 and verbose):
            print("Total reservations: {} and total dispatches: {}".format(total_reservations, total_dispatches))
            print(len(list(traci.vehicle.getTaxiFleet(taxi_states.any_state.value))))

        # Get list of idle taxis and reservations
        idle_taxi_ids = list(traci.vehicle.getTaxiFleet(taxi_states.empty.value))
        idle_taxis = [taxi for taxi in taxis if taxi.id in idle_taxi_ids]
        new_reservations = list(traci.person.getTaxiReservations(reservation_states.new.value))
        reservations_queue.extend(new_reservations)
        total_reservations += len(new_reservations)

        # Deal with queue of reservations
        for reservation in reservations_queue:
            if (len(idle_taxis) > 0):
                taxi = get_available_taxi(reservation, idle_taxis)
                if (taxi != None):
                    reservations_queue.remove(reservation)
                    idle_taxis.remove(taxi)
                    taxi.pickup = [reservation.id, reservation.id]
                    if (verbose):
                        print('dispatched taxi {} for reservation {}'.format(taxi.id, reservation.id))
                    traci.vehicle.dispatchTaxi(taxi.id, taxi.pickup)
                    total_dispatches += 1
                else:
                    if (verbose):
                        print('no idle taxi can reach reservation {}'.format(idle_taxis))
    

    # End simulation
    traci.close()

if __name__ == "__main__":
    run()