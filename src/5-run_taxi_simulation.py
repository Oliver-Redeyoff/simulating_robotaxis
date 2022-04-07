from __future__ import absolute_import
from __future__ import print_function
import os
import sys
import math
from typing import List, Dict, Tuple
from tqdm import tqdm
import time
import random
import xml.etree.ElementTree as ET

from datatypes import trip, simulation, taxi_states, reservation_states, Taxi
from utilities import create_dir, retrieve, indent, generate_config

# We need to import python modules from the $SUMO_HOME/tools directory
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
    from sumolib import checkBinary
    import traci
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

# Instantiate global variables
verbose = False
drivable_edges = []
taxis: List[Taxi] = []


# Generates the file containing the description of the taxis and the trips
def generate_trips_file(trips: List[trip], simulation_: simulation):

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
    
    for trip_ in tqdm(trips):
        person = ET.SubElement(taxi_routes_root, 'person', {
            'id': str(trip_.id), 
            'depart': str(trip_.depart),
            'color': 'green'
        })
        ET.SubElement(person, 'ride', {
            'from': trip_.from_,
            'to': trip_.to,
            'lines': 'taxi'
        })

    taxi_routes_tree = ET.ElementTree(taxi_routes_root)
    indent(taxi_routes_root)
    taxi_routes_tree.write('../temp/' + simulation_.taxi_routes_file, encoding="utf-8", xml_declaration=True)


# Create a new taxi and insert it into the simulation
taxi_count = 0
def new_taxi() -> Taxi:

    global drivable_edges
    global taxis
    global taxi_count
    
    route_id = 'route'+str(taxi_count)
    traci.route.add(route_id, [random.choice(list(drivable_edges))])

    new_taxi = Taxi('v'+str(taxi_count))
    traci.vehicle.add(new_taxi.id, route_id, 'taxi', depart=f'{traci.simulation.getTime()}', line='taxi')
    taxis.append(new_taxi)

    taxi_count += 1
    return new_taxi


# Remove taxi from simulation and replace it with new one
def replace_taxi(taxi) -> Taxi:
    taxis.remove(taxi)
    traci.vehicle.remove(taxi.id)
    replacement_taxi = new_taxi()
    if (verbose):
        print('Replacing taxi {} with {} at time {}'.format(taxi.id, replacement_taxi.id, traci.simulation.getTime()))
    return replacement_taxi


# Taxi dispatch method which just sends the first idle taxi available
def dispatch_taxi_first(reservation, idle_taxis):

    # idle_taxis = get_taxis(taxi_states.idle.value)
    pickup_edge_id = reservation.fromEdge

    for taxi in idle_taxis:
        taxi_edge_id = traci.vehicle.getRoadID(taxi.id)
        route = traci.simulation.findRoute(taxi_edge_id, pickup_edge_id, vType='taxi')
        
        if (route.length != 0):
            return taxi
        else:
            taxi.unreachable_reservations_count += 1
            # Remove taxis which weren't able to reach reservations 10 times
            # as they are probably in some weird spot of the network
            if (taxi.unreachable_reservations_count > 10):
                replace_taxi(taxi)
                idle_taxis.remove(taxi)

    return None


# Taxi dispatch method which sends the closest idle taxi available
def dispatch_taxi_greedy(reservation, idle_taxis):

    pickup_edge_id = reservation.fromEdge
    person_id = reservation.persons[0]
    person_pos = traci.person.getPosition(person_id)
    closest_taxi = (0, None)
    
    for taxi in idle_taxis:
        taxi_pos = traci.vehicle.getPosition(taxi.id)
        dist = math.pow(taxi_pos[0]-person_pos[0], 2) + math.pow(taxi_pos[1]-person_pos[1], 2)
        if (closest_taxi[0] == 0 or dist < closest_taxi[0]):
            taxi_edge_id = traci.vehicle.getRoadID(taxi.id)
            route = None if taxi_edge_id=='' else traci.simulation.findRoute(taxi_edge_id, pickup_edge_id, vType='taxi')
            if (route == None or route.length != 0):
                closest_taxi = (dist, taxi)
            else:
                taxi.unreachable_reservations_count += 1
                # Remove taxis which weren't able to reach reservations 10 times
                # as they are probably in some weird spot of the network
                if (taxi.unreachable_reservations_count > 10):
                    idle_taxis.remove(taxi)
                    replace_taxi(taxi)

    return closest_taxi[1]


# Entrypoint of code
def run():

    global drivable_edges
    global taxis
    global taxi_group_buffers

    # taxis = [Taxi('v'+str(i)) for i in range(taxi_count)]

    # Retrieve data
    trips: List[trip] = retrieve('../temp/trips.pkl')
    drivable_edges = retrieve('../temp/drivable_edges.pkl')
    simulation_: simulation = retrieve('../temp/simulation.pkl')

    # Generate trips file
    generate_trips_file(trips, simulation_)

    # Generate sumo config file and start simulation
    create_dir('../out')
    generate_config(simulation_.net_file, simulation_.taxi_routes_file, simulation_.start_time, simulation_.end_time, '../temp/taxi.sumocfg', True)
    sumoBinary = checkBinary('sumo')
    traci.start([sumoBinary, 
                '--configuration-file', '../temp/taxi.sumocfg',
                '--tripinfo-output', '../out/taxi.tripinfo.xml'])

    # Add taxis to simulation
    taxi_count = 50
    for taxi in range(taxi_count):
        new_taxi()
    print('added taxis')

    # Orchestrate simulation
    reservations_queue = []
    total_reservations = 0
    total_dispatches = 0

    taxi_res_diff = 0
    taxi_res_diff_count = 0

    for _ in tqdm(range(simulation_.start_time, simulation_.end_time)):

        # Move to next simulation step
        traci.simulationStep()
        if (traci.simulation.getTime()%1000 == 0):
            print("Total reservations: {} and total dispatches: {}".format(total_reservations, total_dispatches))
            print(len(list(traci.vehicle.getTaxiFleet(taxi_states.any_state.value))))
            print(taxi_res_diff/taxi_res_diff_count)

        # Get new reservations
        new_reservations = list(traci.person.getTaxiReservations(reservation_states.new.value))
        reservations_queue.extend(new_reservations)
        total_reservations += len(new_reservations)
        
        # Get list of idle taxis
        idle_taxi_ids = traci.vehicle.getTaxiFleet(taxi_states.idle.value)
        idle_taxis = [taxi for taxi in taxis if taxi.id in idle_taxi_ids]

        # Balance the number of taxis
        if (traci.simulation.getTime()%120 == 0 and total_reservations > 0):
            average_diff = taxi_res_diff/taxi_res_diff_count
            # print('difference between number of taxi and reservation : {}'.format(average_diff))
            print()
            print('total taxis in fleet : {}'.format(len(list(traci.vehicle.getTaxiFleet(taxi_states.any_state.value)))))
            # print('total reservations : {}'.format(total_reservations))

            if (abs(average_diff) > 10):
                # if diff is negative, remove taxis
                if (average_diff < 0):
                    print('removing {} taxis'.format(round(average_diff)))
                    for i in range(abs(round(average_diff))):
                        if (len(idle_taxis) > 0):
                            taxi = random.choice(idle_taxis)
                            taxis.remove(taxi)
                            traci.vehicle.remove(taxi.id)
                            print(taxi in idle_taxis)
                            idle_taxis.remove(taxi)
                elif (average_diff > 0):
                    print('adding {} taxis'.format(round(average_diff)))
                    for i in range(round(average_diff)):
                        new_taxi()

            # print('new total taxis in fleet : {}'.format(len(list(traci.vehicle.getTaxiFleet(taxi_states.any_state.value)))))
            print()
            taxi_res_diff = 0
            taxi_res_diff_count = 0

        # Deal with queue of reservations
        for reservation in reservations_queue:

            # Decide which taxi to dispatch to reservation
            taxi = dispatch_taxi_greedy(reservation, idle_taxis)
            
            # Actually dispatch that taxi
            if (taxi != None):
                taxi.pickup = [reservation.id, reservation.id]

                try:
                    traci.vehicle.dispatchTaxi(taxi.id, taxi.pickup)
                    if (verbose):
                        print('dispatched taxi {} for reservation {}'.format(taxi.id, reservation.id))
                    total_dispatches += 1
                    reservations_queue.remove(reservation)
                    idle_taxis.remove(taxi)
                except:
                    if (verbose):
                        print("couldn't dispatch taxi {} for reservation {} at time {}".format(taxi.id, reservation.id, traci.simulation.getTime()))

        taxi_res_diff += len(reservations_queue)-len(idle_taxis)
        taxi_res_diff_count += 1

    # End simulation
    traci.close()


if __name__ == "__main__":
    run()