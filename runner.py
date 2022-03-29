from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import optparse
import random

# we need to import python modules from the $SUMO_HOME/tools directory
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

from sumolib import checkBinary
import traci

def createTaxis():
    for i in range(0, 20, 5):
        traci.vehicle.add(f'taxi{i}', 'route_0', 'taxi', depart='25200', line='taxi')

if __name__ == "__main__":
    sumoBinary = checkBinary('sumo')
    traci.start([sumoBinary, "-c", "target.sumocfg"])
    createTaxis()
    fleet = traci.vehicle.getTaxiFleet(0)
    reservations = traci.person.getTaxiReservations(0)
    print(reservations)
    reservation_ids = [r.id for r in reservations]
    traci.vehicle.dispatchTaxi(fleet[0], reservation_ids[0])