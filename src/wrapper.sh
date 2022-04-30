echo "--RETRIEVING DATA--"
python3 0-get_data.py
echo ""

echo "--PREPARING DATA--"
python3 1-prepare_data.py >/dev/null 2>&1
echo ""

echo "--GENERATING MOBILITY DEMAND--"
python3 2-generate_demand.py
echo ""

echo "--RUNNING BASE SIMULATION--"
python3 3-run_base_simulation.py
echo ""

echo "--RUNNING TAXI SIMULATION--"
python3 4-run_taxi_simulation.py
echo ""