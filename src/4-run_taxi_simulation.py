from __future__ import absolute_import
from __future__ import print_function
import os
import sys
import math
import time
from typing import List
import random
import xml.etree.ElementTree as ET

from tqdm import tqdm

from datatypes import Trip, Simulation, TaxiStates, ReservationStates, Taxi, TaxiSimulationLog
from utilities import create_dir, store, retrieve, indent, generate_config

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
def generate_trips_file(trips: List[Trip], simulation: Simulation):

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
    
    for trip in tqdm(trips):
        person = ET.SubElement(taxi_routes_root, 'person', {
            'id': str(trip.id), 
            'depart': str(trip.depart),
            'color': 'green'
        })
        ET.SubElement(person, 'ride', {
            'from': trip.from_,
            'to': trip.to,
            'lines': 'taxi'
        })

    taxi_routes_tree = ET.ElementTree(taxi_routes_root)
    indent(taxi_routes_root)
    taxi_routes_tree.write('../temp/' + simulation.taxi_routes_file, encoding="utf-8", xml_declaration=True)


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

    # Retrieve data
    trips: List[Trip] = retrieve('../temp/trips.pkl')
    drivable_edges = retrieve('../temp/drivable_edges.pkl')
    simulation: Simulation = retrieve('../temp/simulation.pkl')

    # Generate trips file
    generate_trips_file(trips, simulation)

    # Generate sumo config file and start simulation
    generate_config(simulation.net_file, simulation.taxi_routes_file, simulation.start_time, simulation.end_time, '../temp/taxi.sumocfg', True)
    sumoBinary = checkBinary('sumo')
    traci.start([sumoBinary, 
                '--configuration-file', '../temp/taxi.sumocfg',
                '--tripinfo-output', '../temp/taxi.tripinfo.xml'])
    simulation_log: List[TaxiSimulationLog] = []

    # Add taxis to simulation
    taxi_count = 100
    for taxi in range(taxi_count):
        new_taxi()

    # Orchestrate simulation
    reservations_queue = []
    total_reservations = 0
    total_dispatches = 0
    idle_taxi_counts = []
    reservation_queue_counts = []

    for _ in tqdm(range(simulation.start_time, simulation.end_time+1200)):

        # Move to next simulation step
        traci.simulationStep()

        if (traci.simulation.getTime()%120 == 0):
            # Remove taxis from our list that have mysteriously disapeared
            taxis = [taxi for taxi in taxis if taxi.id in traci.vehicle.getTaxiFleet(TaxiStates.any_state.value)]

            # Store simulation logs
            simulation_log.append(TaxiSimulationLog(
                traci.simulation.getTime(),
                len(taxis),
                total_reservations,
                total_dispatches,
                sum(idle_taxi_counts)/len(idle_taxi_counts)
            ))

            # Print out info
            if (verbose):
                print("Total reservations: {} and total dispatches: {}".format(total_reservations, total_dispatches))
                print("Total taxis: {}".format(len(taxis)))
                print("Idle taxis average: {}".format(sum(idle_taxi_counts)/len(idle_taxi_counts)))
                print("Reservation queue average: {}".format(sum(reservation_queue_counts)/len(reservation_queue_counts)))

            # Reset stuff
            idle_taxi_counts = []
            reservation_queue_counts = []

        # Get new reservations
        new_reservations = list(traci.person.getTaxiReservations(ReservationStates.new.value))
        reservations_queue.extend(new_reservations)
        total_reservations += len(new_reservations)
        reservation_queue_counts.append(len(reservations_queue))
        
        # Get list of idle taxis
        idle_taxi_ids = traci.vehicle.getTaxiFleet(TaxiStates.idle.value)
        idle_taxis = [taxi for taxi in taxis if taxi.id in idle_taxi_ids]
        idle_taxi_counts.append(len(idle_taxis))

        # Deal with queue of reservations
        for reservation in reservations_queue:

            # Decide which taxi to dispatch to reservation
            taxi = dispatch_taxi_greedy(reservation, idle_taxis)
            
            # Actually dispatch that taxi
            if (taxi != None):
                try:
                    taxi.pickup = [reservation.id, reservation.id]
                    traci.vehicle.dispatchTaxi(taxi.id, taxi.pickup)
                    if (verbose):
                        print('Dispatched taxi {} for reservation {}'.format(taxi.id, reservation.id))
                    total_dispatches += 1
                    reservations_queue.remove(reservation)
                    idle_taxis.remove(taxi)
                except:
                    if (verbose):
                        print("Failed to dispatch taxi {} for reservation {} at time {}".format(taxi.id, reservation.id, traci.simulation.getTime()))
                    reservations_queue.remove(reservation)
            else:
                if (verbose):
                    print("No available taxi could reach reservation {} at time {}".format(reservation.id, traci.simulation.getTime()))
                reservations_queue.remove(reservation)

        # Update number of taxis in simulation
        if (len(idle_taxis) < 10):
            for i in range(max(50, len(reservations_queue))):
                new_taxi()
        if (len(idle_taxis) > 100):
            taxi = random.choice(idle_taxis)
            taxis.remove(taxi)
            traci.vehicle.remove(taxi.id)
            idle_taxis.remove(taxi)

    # End simulation
    traci.close()

    store(simulation_log, '../temp/taxi_simulation_log.pkl')


if __name__ == "__main__":
    run()