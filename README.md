# warehouse-robotics

Warehouse Robotics Efficiency Program (Simulation + Analytics)

What is this Project?

This project is a simulation of a warehouse environment to demonstrate a pick-path optimization based on distance for time reduction, using a robotic slotting system with a layout strategy in place using an ABC + move list system. The robotics operation includes a monitoring system that helps with fleet utilization, so a robot is always moving, including alerts if a bottleneck occurs.

Why does this matter?

NOTE: Once project has been built

Quickstart

1. pip install -r requirements.txt
2. **Optional** python.exe -m pip install --upgrade pip (for below verison 26.0.1)
3. python src/common/generate_locations.py
4. python src/pick_path/simulate_orders.py
5. python src/pick_path/analyze_routes.py
6. open outputs in /output/
