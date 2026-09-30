# main.py - PicoBot lap counting v1.0
# Based on robosteamdev/picobot-line_following (main.py v17-2).
# The robot follows the line and counts every crossing of the perpendicular marker line.
# Start position: the robot starts BEHIND the marker. The 1st crossing starts lap 1,
# so the robot stops on the marker at crossing number (laps + 1) - right after the last lap.
# ROBO STEAM ACADEMY - Erasmus+ project KA220-VET-7CF4F308
import network
import socket
import json
from time import sleep, ticks_ms, ticks_diff
from machine import Pin, Timer
import picobot_motors

# ------------------------
# AP Setup
# ------------------------
# CHANGE the Wi-Fi name to your own (e.g. 'picobot-team7'), so that you connect to YOUR robot
ssid = 'picobot-lap'
password = '12345678'
led = Pin("LED", Pin.OUT)

ap = network.WLAN(network.AP_IF)
ap.config(essid=ssid, password=password)
ap.active(True)

while ap.active() == False:
    pass

print('Connection successful')
print(ap.ifconfig())
led.on()

# ------------------------
# Motor driver
# ------------------------
motor_driver = picobot_motors.MotorDriver(debug=False)

# ------------------------
# Sensors: right → left
# ------------------------
sensors = [
    Pin(8, Pin.IN, Pin.PULL_UP),   # Right
    Pin(9, Pin.IN, Pin.PULL_UP),   # Right-middle
    Pin(13, Pin.IN, Pin.PULL_UP),  # Center
    Pin(14, Pin.IN, Pin.PULL_UP),  # Left-middle
    Pin(15, Pin.IN, Pin.PULL_UP)   # Left
]

# ------------------------
# Global variables
# ------------------------
robot_running = False
mission_done = False
line_lost = False
line_lost_time = 0
last_direction = "FORWARD"
search_intensity = 1.0  # Start with normal intensity

# ------------------------
# Lap counting
# ------------------------
MARKER_DEBOUNCE_MS = 1000  # after a crossing is counted, ignore the marker for this long (ms)
target_laps = 3            # how many laps to drive (can be changed on the web page)
crossings = 0              # how many times the robot has crossed the marker
laps_done = 0              # completed laps = crossings - 1 (the 1st crossing only starts lap 1)
on_marker = False          # True while the sensors see the marker
last_marker_time = 0       # time (ms) when the last crossing was counted

def reset_lap_counter():
    global crossings, laps_done, on_marker, last_marker_time
    crossings = 0
    laps_done = 0
    on_marker = False
    last_marker_time = 0

def marker_seen(now):
    # Call this when all 5 sensors see the marker.
    # Returns True when the last lap is finished and the robot must stop.
    global crossings, laps_done, on_marker, last_marker_time
    if on_marker:
        return False       # still on the same marker - count it only once
    on_marker = True
    if crossings > 0 and ticks_diff(now, last_marker_time) < MARKER_DEBOUNCE_MS:
        return False       # the sensors flickered on the same marker - ignore
    crossings += 1
    last_marker_time = now
    laps_done = crossings - 1
    print("Marker crossing", crossings, "- laps completed:", laps_done)
    return laps_done >= target_laps

def marker_left():
    # Call this when the sensors do not see the marker any more.
    global on_marker
    on_marker = False

# Default parameters
base_speed = 30
slight_ratio = 0.9
mild_ratio = 0.75
hard_ratio = 0.6
grace_period = 800  # Increased grace period for sharp turns
search_ratio = 0.4  # Ratio for aggressive searching

# ------------------------
# HTML and JS content
# ------------------------
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PicoBot Lap Counter</title>
<link rel="stylesheet" href="/style.css">
</head>
<body>
<h1>PicoBot Lap Counter</h1>

<div class="status-panel">
    <div class="section-title">Robot Status</div>
    <div class="sensor-container">
        <div class="sensor-box" id="left">L</div>
        <div class="sensor-box" id="lmid">LM</div>
        <div class="sensor-box" id="center">C</div>
        <div class="sensor-box" id="rmid">RM</div>
        <div class="sensor-box" id="right">R</div>
    </div>
    <div class="status-container">
        <div id="action">Action: -</div>
        <div id="status">Status: -</div>
        <div id="laps_info">Laps: 0 / 3</div>
    </div>
</div>

<div class="control-panel">
    <div class="section-title">Robot Control</div>
    <div>
        <button class="start-btn" id="startBtn">START</button>
        <button class="stop-btn" id="stopBtn">STOP</button>
    </div>
    <div class="section-title">Adjustments</div>
    <div class="param-group">
        <div class="param"><div class="label">Speed</div><input type="number" id="speed" value="30" min="0" max="100"></div>
        <div class="param"><div class="label">Slight</div><input type="number" id="slight" value="0.9" step="0.05" min="0" max="1"></div>
        <div class="param"><div class="label">Mild</div><input type="number" id="mild" value="0.75" step="0.05" min="0" max="1"></div>
        <div class="param"><div class="label">Hard</div><input type="number" id="hard" value="0.6" step="0.05" min="0" max="1"></div>
        <div class="param"><div class="label">Grace (ms)</div><input type="number" id="grace" value="800" min="0" max="5000"></div>
        <div class="param"><div class="label">Search</div><input type="number" id="search" value="0.4" step="0.05" min="0" max="1"></div>
        <div class="param"><div class="label">Laps</div><input type="number" id="laps" value="3" min="1" max="99"></div>
    </div>
    <button class="update-btn" id="updateBtn">Update Parameters</button>
</div>

<script src="/script.js"></script>
</body>
</html>"""

css_content = """body { 
    font-family: Arial, sans-serif; 
    text-align: center; 
    margin: 0;
    padding: 10px;
    background-color: #f0f0f0;
}
.status-panel {
    background-color: white;
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    margin-bottom: 15px;
}
.control-panel {
    background-color: white;
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    margin-bottom: 15px;
}
.param-group {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 10px;
    margin: 10px 0;
}
.param {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 80px;
}
button { 
    font-size: 1.5em; 
    padding: 15px 30px; 
    margin: 10px;
    min-width: 120px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
}
.start-btn {
    background-color: #4CAF50;
    color: white;
}
.stop-btn {
    background-color: #f44336;
    color: white;
}
.update-btn {
    background-color: #2196F3;
    color: white;
    font-size: 1.2em;
    padding: 10px 20px;
}
input[type=number] { 
    font-size: 1.2em; 
    width: 80px; 
    text-align: center;
    padding: 5px;
    border: 1px solid #ccc;
    border-radius: 4px;
}
.sensor-container {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    margin: 15px 0;
}
.sensor-box { 
    width: 50px; 
    height: 50px; 
    line-height: 50px; 
    margin: 5px; 
    border: 2px solid #000; 
    font-weight: bold; 
    font-size: 1.2em;
    border-radius: 8px;
}
.status-container {
    margin: 15px 0;
    font-size: 1.2em;
}
#action, #status, #laps_info {
    margin: 8px 0;
    font-weight: bold;
    padding: 8px;
    border-radius: 5px;
    background-color: #f8f8f8;
}
.label {
    font-weight: bold;
    margin-bottom: 5px;
    font-size: 0.9em;
}
.section-title {
    font-size: 1.3em;
    font-weight: bold;
    margin: 10px 0;
    color: #333;
}"""

js_content = """// Initialize with current parameters
function loadParams() {
    fetch("/sensors")
    .then(response => response.json())
    .then(data => {
        if (data.params) {
            document.getElementById("speed").value = data.params.speed || 30;
            document.getElementById("slight").value = data.params.slight || 0.9;
            document.getElementById("mild").value = data.params.mild || 0.75;
            document.getElementById("hard").value = data.params.hard || 0.6;
            document.getElementById("grace").value = data.params.grace || 800;
            document.getElementById("search").value = data.params.search || 0.4;
            document.getElementById("laps").value = data.params.laps || 3;
        }
    })
    .catch(err => console.log("Error loading params:", err));
}

function startRobot() {
    const speed = document.getElementById("speed").value;
    const slight = document.getElementById("slight").value;
    const mild = document.getElementById("mild").value;
    const hard = document.getElementById("hard").value;
    const grace = document.getElementById("grace").value;
    const search = document.getElementById("search").value;
    const laps = document.getElementById("laps").value;
    
    fetch("/?action=start&speed=" + speed + "&slight=" + slight + "&mild=" + mild + "&hard=" + hard + "&grace=" + grace + "&search=" + search + "&laps=" + laps);
}

function stopRobot() {
    fetch("/?action=stop");
}

function updateParams() {
    const speed = document.getElementById("speed").value;
    const slight = document.getElementById("slight").value;
    const mild = document.getElementById("mild").value;
    const hard = document.getElementById("hard").value;
    const grace = document.getElementById("grace").value;
    const search = document.getElementById("search").value;
    const laps = document.getElementById("laps").value;
    
    fetch("/?action=update&speed=" + speed + "&slight=" + slight + "&mild=" + mild + "&hard=" + hard + "&grace=" + grace + "&search=" + search + "&laps=" + laps);
}

function updateSensors() {
    fetch("/sensors")
    .then(response => response.json())
    .then(data => {
        let vals = data.sensors;
        document.getElementById("left").style.backgroundColor = vals[4]==1?"green":"white";
        document.getElementById("lmid").style.backgroundColor = vals[3]==1?"green":"white";
        document.getElementById("center").style.backgroundColor = vals[2]==1?"green":"white";
        document.getElementById("rmid").style.backgroundColor = vals[1]==1?"green":"white";
        document.getElementById("right").style.backgroundColor = vals[0]==1?"green":"white";

        document.getElementById("action").innerText = "Action: "+data.action;
        document.getElementById("status").innerText = "Status: "+data.status;
        document.getElementById("laps_info").innerText = "Laps: " + data.laps_done + " / " + data.target_laps;
        
        // Color code the status based on state
        const statusElem = document.getElementById("status");
        if (data.status.includes("Running")) {
            statusElem.style.color = "green";
        } else if (data.status.includes("Stopped") || data.status.includes("Finished")) {
            statusElem.style.color = "blue";
        } else if (data.status.includes("lost")) {
            statusElem.style.color = "orange";
        } else {
            statusElem.style.color = "black";
        }
    })
    .catch(err => console.log("Sensor update error:", err));
}

// Set up event listeners
document.getElementById("startBtn").addEventListener("click", startRobot);
document.getElementById("stopBtn").addEventListener("click", stopRobot);
document.getElementById("updateBtn").addEventListener("click", updateParams);

// Load parameters on page load and poll sensors every 200ms
window.addEventListener("load", function() {
    loadParams();
    setInterval(updateSensors, 200);
});"""

# ------------------------
# Decide action
# ------------------------
def decide_action(sensor_values):
    if all(v == 1 for v in sensor_values):
        return "ON JUNCTION"
    if all(v == 0 for v in sensor_values):
        return "LINE LOST"
    
    positions = [2, 1, 0, -1, -2]
    weighted_sum = 0
    active_sensors = 0
    
    for i in range(5):
        if sensor_values[i] == 1:
            weighted_sum += positions[i]
            active_sensors += 1
    
    if active_sensors > 0:
        weighted_sum = weighted_sum / active_sensors
    
    if weighted_sum > 1.2:
        return "HARD RIGHT"
    elif weighted_sum > 0.6:
        return "MILD RIGHT"
    elif weighted_sum > 0.2:
        return "SLIGHT RIGHT"
    elif weighted_sum < -1.2:
        return "HARD LEFT"
    elif weighted_sum < -0.6:
        return "MILD LEFT"
    elif weighted_sum < -0.2:
        return "SLIGHT LEFT"
    elif weighted_sum == 0 and any(v == 1 for v in sensor_values):
        return "FORWARD"
    else:
        return "SEARCHING"

# ------------------------
# Map action to motor speeds with aggressive line loss recovery
# ------------------------
def set_motor_action(action):
    global last_direction, search_intensity
    
    if action == "FORWARD":
        motor_driver.TurnMotor('LeftFront', 'forward', base_speed)
        motor_driver.TurnMotor('LeftBack', 'forward', base_speed)
        motor_driver.TurnMotor('RightFront', 'forward', base_speed)
        motor_driver.TurnMotor('RightBack', 'forward', base_speed)
        search_intensity = 1.0  # Reset search intensity
        
    elif action == "SLIGHT RIGHT":
        motor_driver.TurnMotor('LeftFront', 'forward', base_speed)
        motor_driver.TurnMotor('LeftBack', 'forward', base_speed)
        motor_driver.TurnMotor('RightFront', 'forward', int(base_speed * slight_ratio))
        motor_driver.TurnMotor('RightBack', 'forward', int(base_speed * slight_ratio))
        search_intensity = 1.0  # Reset search intensity
        
    elif action == "MILD RIGHT":
        motor_driver.TurnMotor('LeftFront', 'forward', base_speed)
        motor_driver.TurnMotor('LeftBack', 'forward', base_speed)
        motor_driver.TurnMotor('RightFront', 'forward', int(base_speed * mild_ratio))
        motor_driver.TurnMotor('RightBack', 'forward', int(base_speed * mild_ratio))
        search_intensity = 1.0  # Reset search intensity
        
    elif action == "HARD RIGHT":
        motor_driver.TurnMotor('LeftFront', 'forward', base_speed)
        motor_driver.TurnMotor('LeftBack', 'forward', base_speed)
        motor_driver.TurnMotor('RightFront', 'forward', int(base_speed * hard_ratio))
        motor_driver.TurnMotor('RightBack', 'forward', int(base_speed * hard_ratio))
        search_intensity = 1.0  # Reset search intensity
        
    elif action == "SLIGHT LEFT":
        motor_driver.TurnMotor('LeftFront', 'forward', int(base_speed * slight_ratio))
        motor_driver.TurnMotor('LeftBack', 'forward', int(base_speed * slight_ratio))
        motor_driver.TurnMotor('RightFront', 'forward', base_speed)
        motor_driver.TurnMotor('RightBack', 'forward', base_speed)
        search_intensity = 1.0  # Reset search intensity
        
    elif action == "MILD LEFT":
        motor_driver.TurnMotor('LeftFront', 'forward', int(base_speed * mild_ratio))
        motor_driver.TurnMotor('LeftBack', 'forward', int(base_speed * mild_ratio))
        motor_driver.TurnMotor('RightFront', 'forward', base_speed)
        motor_driver.TurnMotor('RightBack', 'forward', base_speed)
        search_intensity = 1.0  # Reset search intensity
        
    elif action == "HARD LEFT":
        motor_driver.TurnMotor('LeftFront', 'forward', int(base_speed * hard_ratio))
        motor_driver.TurnMotor('LeftBack', 'forward', int(base_speed * hard_ratio))
        motor_driver.TurnMotor('RightFront', 'forward', base_speed)
        motor_driver.TurnMotor('RightBack', 'forward', base_speed)
        search_intensity = 1.0  # Reset search intensity
        
    elif action == "ON JUNCTION":
        motor_driver.StopAllMotors()
        search_intensity = 1.0  # Reset search intensity
        
    elif action == "LINE LOST":
        # Increase search intensity each time we lose the line for sharper turns
        search_intensity *= 1.5
        
        # Aggressive turning when line is lost - much sharper turns
        if ticks_diff(ticks_ms(), line_lost_time) < grace_period:
            if "RIGHT" in last_direction:
                # Very sharp right turn search
                turn_speed = int(base_speed * search_ratio * search_intensity)
                motor_driver.TurnMotor('LeftFront', 'forward', turn_speed)
                motor_driver.TurnMotor('LeftBack', 'forward', turn_speed)
                motor_driver.TurnMotor('RightFront', 'backward', turn_speed)
                motor_driver.TurnMotor('RightBack', 'backward', turn_speed)
            elif "LEFT" in last_direction:
                # Very sharp left turn search
                turn_speed = int(base_speed * search_ratio * search_intensity)
                motor_driver.TurnMotor('LeftFront', 'backward', turn_speed)
                motor_driver.TurnMotor('LeftBack', 'backward', turn_speed)
                motor_driver.TurnMotor('RightFront', 'forward', turn_speed)
                motor_driver.TurnMotor('RightBack', 'forward', turn_speed)
            else:
                # Forward was last direction, do gentle search
                set_motor_action(last_direction)
        else:
            motor_driver.StopAllMotors()
            search_intensity = 1.0  # Reset search intensity
            
    elif action == "SEARCHING":
        # Use the same aggressive search pattern as LINE LOST
        if ticks_diff(ticks_ms(), line_lost_time) < grace_period:
            if "RIGHT" in last_direction:
                turn_speed = int(base_speed * search_ratio * search_intensity)
                motor_driver.TurnMotor('LeftFront', 'forward', turn_speed)
                motor_driver.TurnMotor('LeftBack', 'forward', turn_speed)
                motor_driver.TurnMotor('RightFront', 'backward', turn_speed)
                motor_driver.TurnMotor('RightBack', 'backward', turn_speed)
            elif "LEFT" in last_direction:
                turn_speed = int(base_speed * search_ratio * search_intensity)
                motor_driver.TurnMotor('LeftFront', 'backward', turn_speed)
                motor_driver.TurnMotor('LeftBack', 'backward', turn_speed)
                motor_driver.TurnMotor('RightFront', 'forward', turn_speed)
                motor_driver.TurnMotor('RightBack', 'forward', turn_speed)
            else:
                set_motor_action(last_direction)
        else:
            motor_driver.StopAllMotors()
            search_intensity = 1.0  # Reset search intensity
    
    # Update last direction if not line lost or searching
    if action not in ["LINE LOST", "SEARCHING"]:
        last_direction = action

# ------------------------
# Open socket
# ------------------------
def open_socket(ip):
    addr = socket.getaddrinfo(ip, 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    return s

# ------------------------
# Main
# ------------------------
ap_ip = ap.ifconfig()[0]
sock = open_socket(ap_ip)
print("Server running on:", ap_ip)

# Timer for line following
line_follow_timer = Timer()

def line_follow_callback(timer):
    global robot_running, mission_done, line_lost, line_lost_time
    
    if not robot_running:
        return
        
    vals = [s.value() for s in sensors]
    act = decide_action(vals)
    
    if act != "ON JUNCTION":
        marker_left()

    if act == "ON JUNCTION":
        if marker_seen(ticks_ms()):
            # Last lap finished - stop on the marker
            motor_driver.StopAllMotors()
            mission_done = True
            robot_running = False
            print("Finished -", laps_done, "laps completed")
        else:
            # Not finished yet - drive straight over the marker
            set_motor_action("FORWARD")
        
    elif act == "LINE LOST":
        if not line_lost:
            line_lost = True
            line_lost_time = ticks_ms()
            print("Line lost - starting aggressive search")
        elif ticks_diff(ticks_ms(), line_lost_time) >= grace_period:
            motor_driver.StopAllMotors()
            print("Line lost - stopped after grace period")
        else:
            # Continue with aggressive search during grace period
            set_motor_action(act)
            
    else:
        if line_lost:
            line_lost = False
            print("Line found - resuming normal operation")
        
        # Set motors based on action
        set_motor_action(act)
    
    print("Sensors:", vals, "Action:", act, "Search intensity:", search_intensity)

line_follow_timer.init(period=50, mode=Timer.PERIODIC, callback=line_follow_callback)

while True:
    try:
        client, addr = sock.accept()
        request = client.recv(1024)
        request_str = request.decode()
        print("Request:", request_str)

        # Handle sensor requests
        if "GET /sensors" in request_str:
            vals = [s.value() for s in sensors]
            act = decide_action(vals)
            
            if mission_done:
                status = "Finished: " + str(laps_done) + " laps"
            elif line_lost and ticks_diff(ticks_ms(), line_lost_time) >= grace_period:
                status = "Line lost - stopped"
            elif line_lost:
                status = "Line lost - searching"
            elif robot_running:
                if crossings == 0:
                    status = "Running - driving to the marker"
                else:
                    status = "Running - lap " + str(laps_done + 1) + " of " + str(target_laps)
            else:
                status = "Stopped"

            data = {
                'sensors': vals, 
                'action': act, 
                'status': status,
                'crossings': crossings,
                'laps_done': laps_done,
                'target_laps': target_laps,
                'params': {
                    'speed': base_speed,
                    'slight': slight_ratio,
                    'mild': mild_ratio,
                    'hard': hard_ratio,
                    'grace': grace_period,
                    'search': search_ratio,
                    'laps': target_laps
                }
            }
            
            # Proper HTTP response with CORS headers
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: application/json\r\n"
            response += "Access-Control-Allow-Origin: *\r\n"
            response += "Connection: close\r\n\r\n"
            response += json.dumps(data)
            
            client.send(response.encode())
            
        # Handle control actions
        elif "GET /?action=start" in request_str:
            robot_running = True
            mission_done = False
            line_lost = False
            search_intensity = 1.0  # Reset search intensity
            reset_lap_counter()
            
            # Extract parameters
            if "speed=" in request_str:
                base_speed = int(request_str.split("speed=")[1].split("&")[0].split(" ")[0])
            if "slight=" in request_str:
                slight_ratio = float(request_str.split("slight=")[1].split("&")[0].split(" ")[0])
            if "mild=" in request_str:
                mild_ratio = float(request_str.split("mild=")[1].split("&")[0].split(" ")[0])
            if "hard=" in request_str:
                hard_ratio = float(request_str.split("hard=")[1].split("&")[0].split(" ")[0])
            if "grace=" in request_str:
                grace_period = int(request_str.split("grace=")[1].split("&")[0].split(" ")[0])
            if "search=" in request_str:
                search_ratio = float(request_str.split("search=")[1].split("&")[0].split(" ")[0])
            if "laps=" in request_str:
                target_laps = max(1, int(request_str.split("laps=")[1].split("&")[0].split(" ")[0]))
            
            print(f"Starting with speed={base_speed}, ratios: slight={slight_ratio}, mild={mild_ratio}, hard={hard_ratio}, grace={grace_period}, search={search_ratio}")
            
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: text/plain\r\n"
            response += "Access-Control-Allow-Origin: *\r\n"
            response += "Connection: close\r\n\r\n"
            response += "OK"
            
            client.send(response.encode())
            
        elif "GET /?action=stop" in request_str:
            robot_running = False
            motor_driver.StopAllMotors()
            search_intensity = 1.0  # Reset search intensity
            print("Stopped by user")
            
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: text/plain\r\n"
            response += "Access-Control-Allow-Origin: *\r\n"
            response += "Connection: close\r\n\r\n"
            response += "OK"
            
            client.send(response.encode())
            
        elif "GET /?action=update" in request_str:
            # Update parameters without starting the robot
            if "speed=" in request_str:
                base_speed = int(request_str.split("speed=")[1].split("&")[0].split(" ")[0])
            if "slight=" in request_str:
                slight_ratio = float(request_str.split("slight=")[1].split("&")[0].split(" ")[0])
            if "mild=" in request_str:
                mild_ratio = float(request_str.split("mild=")[1].split("&")[0].split(" ")[0])
            if "hard=" in request_str:
                hard_ratio = float(request_str.split("hard=")[1].split("&")[0].split(" ")[0])
            if "grace=" in request_str:
                grace_period = int(request_str.split("grace=")[1].split("&")[0].split(" ")[0])
            if "search=" in request_str:
                search_ratio = float(request_str.split("search=")[1].split("&")[0].split(" ")[0])
            if "laps=" in request_str:
                target_laps = max(1, int(request_str.split("laps=")[1].split("&")[0].split(" ")[0]))
            
            print(f"Updated parameters: speed={base_speed}, ratios: slight={slight_ratio}, mild={mild_ratio}, hard={hard_ratio}, grace={grace_period}, search={search_ratio}")
            
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: text/plain\r\n"
            response += "Access-Control-Allow-Origin: *\r\n"
            response += "Connection: close\r\n\r\n"
            response += "OK"
            
            client.send(response.encode())
            
        # Serve CSS file
        elif "GET /style.css" in request_str:
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: text/css\r\n"
            response += "Access-Control-Allow-Origin: *\r\n"
            response += "Connection: close\r\n\r\n"
            response += css_content
            
            client.send(response.encode())
            
        # Serve JavaScript file
        elif "GET /script.js" in request_str:
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: application/javascript\r\n"
            response += "Access-Control-Allow-Origin: *\r\n"
            response += "Connection: close\r\n\r\n"
            response += js_content
            
            client.send(response.encode())
            
        else:
            # Serve HTML page
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: text/html\r\n"
            response += "Access-Control-Allow-Origin: *\r\n"
            response += "Connection: close\r\n\r\n"
            response += html_content
            
            client.send(response.encode())

        client.close()

    except Exception as e:
        print("Error:", e)
        try:
            client.close()
        except:
            pass