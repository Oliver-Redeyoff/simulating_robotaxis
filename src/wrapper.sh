rm -r ../temp

echo "--RETRIEVING DATA--"
python3 0-get_data.py
echo ""

echo "--GENERATING TAZ--"
python3 1-generate_taz.py >/dev/null 2>&1
echo ""

echo "--FILTERING COUNT POINTS--"
python3 2-filter_count_points.py
echo ""

echo "--GENERATING MOBILITY DEMAND--"
python3 3-generate_demand.py
echo ""

echo "--RUNNING BASE SIMULATION--"
python3 4-run_base_simulation.py
echo ""

echo "--RUNNING TAXI SIMULATION--"
python3 5-run_taxi_simulation.py
echo ""