from __future__ import absolute_import
from __future__ import print_function
import os
import sys
from typing import List, Dict
from tqdm import tqdm
import random
import xml.etree.ElementTree as ET

from datatypes import trip, simulation, taxi_states, reservation_states, Taxi, TaxiGroupBuffer
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
verbose = True
taxis: List[Taxi] = []
reservations_queue = []
taxi_group_buffers: Dict[int, TaxiGroupBuffer] = {}


# Gets all taxis in a given state, stores results in a buffer
def get_taxis(state: int) -> List[Taxi]:

    global taxis
    global taxi_group_buffer

    current_time = traci.simulation.getTime()
    if (state not in taxi_group_buffers):
        requested_taxi_ids = list(traci.vehicle.getTaxiFleet(state))
        requested_taxis = [taxi for taxi in taxis if taxi.id in requested_taxi_ids]
        taxi_group_buffers[state] = TaxiGroupBuffer(
            state,
            requested_taxis,
            current_time
        )
        return taxi_group_buffers[state].taxis
    else:
        taxi_group_buffer = taxi_group_buffers[state]
        if (taxi_group_buffer.last_checked == current_time):
            return taxi_group_buffer.taxis
        else :
            requested_taxi_ids = list(traci.vehicle.getTaxiFleet(state))
            requested_taxis = [taxi for taxi in taxis if taxi.id in requested_taxi_ids]
            taxi_group_buffer.taxis = requested_taxis
            taxi_group_buffer.last_checked = current_time
            return taxi_group_buffer.taxis


# Signals that taxi couldn't find a route, after 10 times the taxi is removed
def taxi_has_no_route(taxi):

    global taxis

    taxi.unreachable_reservations_count += 1
    # Remove taxis which weren't able to reach reservations 10 times
    # as they are probably in some weird spot of the network
    if (taxi.unreachable_reservations_count > 10):
        if (verbose):
            print('Removing taxi ' + taxi.id)
        taxis.remove(taxi)
        traci.vehicle.remove(taxi.id)
        for _, taxi_group_buffer in taxi_group_buffers.items():
            taxi_group_buffer.taxis.remove(taxi)


# Generates the file containing the description of the taxis and the trips
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


# Taxi dispatch method which just sends the first idle taxi available
def dispatch_taxi_first(reservation):

    idle_taxis = get_taxis(taxi_states.idle.value)

    for taxi in idle_taxis:
        taxi_edge_id = traci.vehicle.getRoadID(taxi.id)
        pickup_edge_id = reservation.fromEdge

        route = traci.simulation.findRoute(taxi_edge_id, pickup_edge_id, vType='taxi')
        
        if (route.length != 0):
            return taxi
        else:
            taxi_has_no_route(taxi)

    return None


# Taxi dispatch method which sends the closest idle taxi available
def dispatch_taxi_greedy(reservation):
    # traci.vehicle.getPosition(id)
    # traci.person.getPosition(id)
    pass


# Entrypoint of code
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

    print(traci.simulation.getNetBoundary())

    # Orchestrate simulation
    total_reservations = 0
    total_dispatches = 0
    for _ in tqdm(range(simulation_.start_time, simulation_.end_time)):

        # Move to next simulation step
        traci.simulationStep()
        if (traci.simulation.getTime()%100 == 0 and verbose):
            print("Total reservations: {} and total dispatches: {}".format(total_reservations, total_dispatches))
            print(len(list(traci.vehicle.getTaxiFleet(taxi_states.any_state.value))))

        # Get new reservations
        new_reservations = list(traci.person.getTaxiReservations(reservation_states.new.value))
        reservations_queue.extend(new_reservations)
        total_reservations += len(new_reservations)

        # Deal with queue of reservations
        for reservation in reservations_queue:

            # Decide which taxi to dispatch to reservation
            taxi = dispatch_taxi_first(reservation)
            
            # Actually dispatch that taxi
            if (taxi != None):
                reservations_queue.remove(reservation)
                get_taxis(taxi_states.idle.value).remove(taxi)
                taxi.pickup = [reservation.id, reservation.id]
                if (verbose):
                    print('dispatched taxi {} for reservation {}'.format(taxi.id, reservation.id))
                traci.vehicle.dispatchTaxi(taxi.id, taxi.pickup)
                total_dispatches += 1
            else:
                if (verbose):
                    print('no idle taxi can reach reservation')
    

    # End simulation
    traci.close()


if __name__ == "__main__":
    run()