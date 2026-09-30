# picobot-lap-counting

![Co-funded by the European Union · ROBO STEAM ACADEMY · partner logos](images/logos_strip.png)

**Erasmus+ project ROBO STEAM ACADEMY** (KA220-VET-7CF4F308) — co-funded by the European Union — <https://robosteam.eu/>

Part of the **PicoBot Teachers' Toolkit** (lesson plans, student materials, slides and guides in five languages):
<https://github.com/robosteamdev/robo-steam-academy-teachers-toolkit>

PicoBot follows a black line and **counts the laps** by detecting a perpendicular marker line across the track.
It stops automatically after the number of laps you choose.

This is the educational project **"Line tracking with number of laps"** of the ROBO STEAM ACADEMY project
(Erasmus+ KA220-VET-7CF4F308, Work Package 2). It is based on
[picobot-line_following](https://github.com/robosteamdev/picobot-line_following).

## How the robot counts
- The marker is a black line **across** the track, wide enough to cover all 5 sensors of the Maker Line at the same time.
- **Start the robot behind the marker.** The 1st crossing starts lap 1. Every next crossing completes one lap.
- The robot stops **on the marker** after the last lap — at crossing number *laps + 1*.
- After a crossing is counted, the marker is ignored for 1 second (`MARKER_DEBOUNCE_MS = 1000`), so one marker is never
  counted twice.

## Files
| File | Upload to the Pico? |
|---|---|
| `main.py` | Yes — the program (starts automatically) |
| `picobot_motors.py` | Yes — motor driver library |

## How to use
1. Open `main.py` in **Thonny** and change the Wi-Fi name to your own, e.g. `ssid = 'picobot-team7'`.
2. Upload `main.py` and `picobot_motors.py` to the Pico.
3. Restart the robot. The onboard LED lights up when the Wi-Fi access point is ready.
4. Connect your phone to your robot's Wi-Fi (password `12345678`) and open **http://192.168.4.1/**.
5. Put the robot on the line, **behind the marker**. Set **Laps** and press **START**.

The page shows the 5 sensors, the current action, the status ("lap 2 of 3") and the lap counter.

## Settings on the web page
| Setting | Meaning | Default |
|---|---|---|
| Speed | Base motor speed, 0–100 % | 30 |
| Slight / Mild / Hard | Speed ratio of the inner wheels for small, medium and sharp corrections | 0.9 / 0.75 / 0.6 |
| Grace (ms) | How long the robot searches for a lost line before it stops | 800 |
| Search | Turning speed ratio while searching for the line | 0.4 |
| **Laps** | Number of laps to drive | 3 |

## Changes compared with picobot-line_following v17-2
- New: lap counter (`reset_lap_counter`, `marker_seen`, `marker_left`), "Laps" setting and lap display on the web page.
- The robot drives straight over the marker instead of stopping at the first one.
- Fixed: the last setting in a START/UPDATE request was not read (the text " HTTP/1.1" was attached to its value).

## Licence and credits
MIT Licence (see `LICENSE`). Please credit "ROBO STEAM ACADEMY, Erasmus+ project KA220-VET-7CF4F308" —
<https://robosteam.eu/>. Used in the PicoBot Teachers' Toolkit (module M11, session 23).

Funded by the European Union. Views and opinions expressed are however those of the author(s) only and do not
necessarily reflect those of the European Union or the Human Resource Development Centre (HRDC). Neither the European
Union nor the granting authority can be held responsible for them.
