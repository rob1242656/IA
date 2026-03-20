# Sonso IA — Bipedal Walking Robot with Reinforcement Learning

A 2D bipedal robot that learns to walk from scratch using **Soft Actor-Critic (SAC)** reinforcement learning. Built with pymunk physics, gymnasium environments, and stable-baselines3.

The robot learns alternating gait (left-right stepping), balance control, and obstacle avoidance — all through trial and error, no hardcoded movement patterns.

## Results

**Best model (V12b — 4M training steps):**

| Metric | Value |
|---|---|
| Episode Length | ~620 steps (10.3 seconds) |
| Episode Reward | +3,145 (avg over 3 episodes) |
| Training Time | ~6 hours on CPU |
| Gait Type | Alternating bipedal walk |

### Training Curve

```
Steps    Reward   Episode Length   Phase
0k       -64      53 steps        Learning to stand
200k     +1,130   934 steps       First walking (fragile)
400k     +377     75 steps        Policy collapse (normal)
600k     +488     223 steps       Recovery
1.0M     +674     125 steps       Stabilizing
1.6M     +1,530   377 steps       Consistent walking
2.0M     +2,310   473 steps       Efficient gait
2.6M     +2,820   587 steps       Near-optimal
3.2M     +2,970   619 steps       Peak performance
4.0M     +1,310   406 steps       Final (re-exploring)
```

Best checkpoint: **3.3M steps** (reward +3,145, ep_len 630)

## Architecture

### Environment (`SonsoEnv`)
- **Physics:** pymunk 2D rigid body simulation (240Hz substeps)
- **Robot:** 5-body articulated figure (torso + 2 thighs + 2 shins)
- **Joints:** 4 motorized joints (2 hips + 2 knees) with torque limits
- **Observation space:** 30 dimensions (proprioception + LIDAR + contacts + goals)
- **Action space:** 4 continuous actions [-1, 1] (joint velocities)

### Reward Function
- **Velocity tracking:** Gaussian reward centered on goal velocity
- **Posture:** Exponential penalty for torso tilt and height deviation
- **Alternating gait:** +2.0 for correct foot alternation, -0.5 for same-foot stepping
- **Rhythmic cadence:** Bonus for 20-80 step intervals between foot contacts
- **Energy efficiency:** L2 penalty on actions + jerk penalty
- **Safety:** Termination on torso/thigh ground contact

### Training Features
- **Domain Randomization:** Gravity (850-950) and friction (0.8-1.2) vary per episode
- **Adaptive Manager:** Goal velocity adjusts based on LIDAR obstacle detection
- **Auto-tuned entropy:** SAC's automatic entropy coefficient (not fixed)
- **Action smoothing:** Exponential moving average (alpha=0.6) for smooth movements
- **Procedural obstacles:** Random height/width boxes spawned ahead of the robot

### Sensor Suite
- **3 LIDAR rays:** Ground distance, far obstacle detection (700px), jump detection
- **Proprioception:** Joint angles, joint velocities, body angular velocity
- **Contact sensors:** Binary foot contact + impact force estimation
- **Previous actions:** Fed back as observation for temporal awareness

## Bugs Fixed (V12b)

12 bugs were identified and fixed from the original codebase:

1. **`ent_coef=0.1` fixed** — Changed to `'auto'` for dynamic entropy tuning
2. **AABB collision missing `medio_w`** — Added width parameter to geometric contact detection
3. **`GROUND_Y=544` incorrect** — Fixed to 545 (segment radius=5 at y=550)
4. **Dead imports (`torch.nn`, `math`)** — Removed to save ~1.6GB RAM across subprocesses
5. **Raycast ShapeFilter fragile XOR** — Changed to proper AND NOT bitmask
6. **Height reference inconsistency** — Aligned observation (450) and reward (460) references
7. **`buffer_size=1M` too large for 16GB RAM** — Reduced to 600K
8. **Double foot contact reward exploit** — Changed `if/if` to `if/elif` to prevent +4.5 reward for simultaneous landing
9. **Missing `device="cpu"`** — Added explicit CPU device for AMD GPU systems
10. **Cadence reward `elif` bug** — Made independent checks for both feet
11. **Bare `except: pass`** — Added specific `ValueError` catch in rendering
12. **Ground friction ignoring DR** — Applied `friccion_dr` to ground segment

## Project Structure

```
.
├── main_ppo.py           # Environment + SAC training (main file)
├── blender_sonso.py      # Blender 5.1 animation export
├── enjoy.py              # Run trained model with visualization
├── simulacion.py         # Simulation runner
├── sonso_v13_design.py   # V13 architecture design (push forces, 512-neuron net)
├── requirements.txt      # Python dependencies
├── Jarvis/               # AI assistant project (Claude API)
└── models/               # Saved checkpoints (not tracked in git)
```

## Quick Start

```bash
# Setup
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt

# Train from scratch (4M steps, ~6h on CPU)
python main_ppo.py

# Watch the trained model walk
python enjoy.py

# Export animation for Blender
python enjoy.py --export
# Then open blender_sonso.py in Blender 5.1 Scripting tab
```

## Hardware Used

- **CPU:** AMD Ryzen 7 5700X (8 cores / 16 threads)
- **GPU:** AMD Radeon RX 570 8GB (not used for training — no CUDA)
- **RAM:** 16 GB DDR4
- **Training:** 6 parallel environments on CPU, ~160-280 FPS

## Tech Stack

- Python 3.10
- [stable-baselines3](https://github.com/DLR-RM/stable-baselines3) (SAC)
- [gymnasium](https://github.com/Farama-Foundation/Gymnasium)
- [pymunk](http://www.pymunk.org/) (2D physics)
- [pygame](https://www.pygame.org/) (visualization)
- [Blender 5.1](https://www.blender.org/) (3D animation export)

## Roadmap

- **V13:** Push force resistance, curriculum learning, 512-neuron network
- **3D Migration:** Move from pymunk 2D to PyBullet/MuJoCo 3D physics
- **GPU Training:** NVIDIA RTX 5070 upgrade planned for CUDA acceleration
- **Blender Integration:** Full 3D rigged character with physics-based animation

## License

MIT
