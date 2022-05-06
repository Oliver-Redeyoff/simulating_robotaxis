# Simulating the Effect of Robotaxi Fleets on Urban Transportation Systems

by Oliver Redeyoff

## Abstract
The field of autonomous vehicles has been rapidly developing over the last few years. The advantages of such vehicles are numerous and span across many industries; in particular, there are clear benefits for the transportation of people. Replacing a human driver with a system that does not experience impairment, and is able to coordinate actions with other vehicles and infrastructure could result in safer and more efficient transportation networks.

One automated option for human transportation is the use of robotaxi fleets, groups of autonomous cars that are operated by a ridesharing company. There are already several companies developing and testing such a service, and based on the popularity of non-automated ridesharing companies such as Uber, these services have the potential to become highly sought after as they would be cheaper and likely provide a more pleasant experience.

It is not too far fetched to imagine a future where some cities would have a fleet of robotaxis as the only available form of transportation for its inhabitants. The question can therefore be raised of how a fleet of robotaxis would perform when having to meet the demand for mobility in an urban setting compared to existing forms of transportation. This paper will explore this subject and attempt to compare the performance of the use of personal vehicles against that of a fleet of robotaxis through simulation.

We will see that robotaxis can not only match the traffic efficiency of personal vehicles, they equally are able to better scale to increased mobility demand and result in reduced necessary infrastructure that could be repurposed.

## Running the code
Firstly, clone this repository:

    git clone https://github.com/Oliver-Redeyoff/simulating_robotaxis.git

This project requires SUMO to be installed, refer to https://github.com/eclipse/sumo for installation instructions.

Python version `3.6` or higher is required, and the following pip packages are equally required:

    folium
    utm
    shapely
    tqdm
    matplotlib
