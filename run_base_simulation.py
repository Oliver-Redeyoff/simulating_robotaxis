import subprocess

def run():
    # Run the simulation using the sumo program

    sumo_options = ['sumo',
                    '--configuration-file', 'target.sumocfg',
                    # '--emission-output', './out/target.emissions.xml',
                    # '--statistic-output', './out/target.stats.xml',
                    '--tripinfo-output', './out/base_target.tripinfo.xml']

    subprocess.check_call(sumo_options)

if __name__ == '__main__':
    run()