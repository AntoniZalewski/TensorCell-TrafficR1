import argparse
import json
import os
import cv2
import numpy as np

# Set matplotlib backend to Agg BEFORE importing pyplot
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, Circle, FancyBboxPatch
from matplotlib.collections import PatchCollection
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import hashlib
import textwrap
import gc
import traceback
from datetime import datetime

# Visual styling constants
COLOR_CANVAS_BG = '#090d16'
COLOR_SIM_BG = '#0b0f19'
COLOR_ROAD = '#1e293b'
COLOR_LANE_DIVIDER = '#475569'
COLOR_LANE_BORDER = '#334155'
COLOR_HUD_BG = '#0d1322'
COLOR_HUD_BORDER = '#1e293b'

# High-visibility vehicle colors
CAR_COLORS = [
    '#38bdf8',  # Electric Cyan
    '#34d399',  # Neon Emerald
    '#fbbf24',  # Amber Glow
    '#c084fc',  # Cyber Violet
    '#f43f5e'   # Vivid Rose
]

def parse_roadnet(roadnet_file):
    with open(roadnet_file, 'r', encoding='utf-8') as f:
        roadnet = json.load(f)
    roads_dict = {r['id']: r for r in roadnet['roads']}
    intersections_dict = {i['id']: i for i in roadnet['intersections']}
    return roadnet, roads_dict, intersections_dict

def parse_replay(replay_file):
    with open(replay_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    return lines

def parse_logs(log_file):
    with open(log_file, 'r', encoding='utf-8') as f:
        logs = json.load(f)
    return logs

def get_intersection_log(logs, intersection_id, step, interval=30, roadnet=None):
    if not logs:
        return None
    # If logs is a 2D list [intersections][steps]
    if isinstance(logs, list) and len(logs) > 0 and isinstance(logs[0], list):
        inter_idx = 0
        if roadnet and 'intersections' in roadnet:
            signalized = [i['id'] for i in roadnet['intersections'] if not i.get('virtual', False)]
            if intersection_id in signalized:
                inter_idx = signalized.index(intersection_id)
        inter_logs = logs[inter_idx] if inter_idx < len(logs) else logs[0]
        step_idx = min(step // interval, len(inter_logs) - 1)
        return inter_logs[step_idx]
    elif isinstance(logs, list):
        step_idx = min(step // interval, len(logs) - 1)
        item = logs[step_idx]
        if isinstance(item, list) and len(item) > 0:
            return item[0]
        return item
    elif isinstance(logs, dict):
        return logs.get(str(step), None)
    return None

def get_vehicle_color(vehicle_id):
    hash_val = int(hashlib.sha256(str(vehicle_id).encode('utf-8')).hexdigest(), 16)
    return CAR_COLORS[hash_val % len(CAR_COLORS)]

def get_road_geometry(road):
    points = road['points']
    p1 = np.array([points[0]['x'], points[0]['y']])
    p2 = np.array([points[1]['x'], points[1]['y']])
    vec = p2 - p1
    length = np.linalg.norm(vec)
    if length == 0: return None
    direction = vec / length
    # Rotate -90 degrees to point to the RIGHT of the road direction
    normal = np.array([direction[1], -direction[0]])
    total_width = sum([l['width'] for l in road['lanes']])
    c1 = p1
    c2 = p1 + normal * total_width
    c3 = p2 + normal * total_width
    c4 = p2
    return [c1, c2, c3, c4]

def get_lane_divider_lines(road):
    points = road['points']
    p1 = np.array([points[0]['x'], points[0]['y']])
    p2 = np.array([points[1]['x'], points[1]['y']])
    vec = p2 - p1
    length = np.linalg.norm(vec)
    if length == 0: return []
    direction = vec / length
    normal = np.array([direction[1], -direction[0]])
    current_width = 0
    lines = []
    for i, lane in enumerate(road['lanes']):
        current_width += lane['width']
        if i < len(road['lanes']) - 1:
            offset = normal * current_width
            lines.append((p1 + offset, p2 + offset))
    return lines

def clean_llm_response(raw_text):
    if not raw_text:
        return 'Initializing agent environment...'
    cleaned = raw_text.replace('!', '').strip()
    return cleaned

def draw_frame(roadnet_data, vehicles, traffic_lights, current_log, step, intersection_id, last_log_entry, action_interval, zoom_level=85):
    roadnet, roads_dict, intersections_dict = roadnet_data
    inter = intersections_dict.get(intersection_id, {})
    cx = inter.get('point', {}).get('x', 0)
    cy = inter.get('point', {}).get('y', 0)
    
    # 1920x1080 Full HD
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(COLOR_CANVAS_BG)
    
    # Left Viewport: Simulation Canvas (61% width)
    ax_sim = fig.add_axes([0.02, 0.03, 0.61, 0.94])
    ax_sim.set_facecolor(COLOR_SIM_BG)
    ax_sim.set_xlim(cx - zoom_level, cx + zoom_level)
    ax_sim.set_ylim(cy - zoom_level, cy + zoom_level)
    ax_sim.set_aspect('equal')
    ax_sim.axis('off')
    
    # Border
    sim_border = FancyBboxPatch((cx - zoom_level, cy - zoom_level), 2*zoom_level, 2*zoom_level,
                                boxstyle='round,pad=0,rounding_size=3',
                                edgecolor='#1f2937', facecolor='none', linewidth=1.5, zorder=10)
    ax_sim.add_patch(sim_border)
    
    # Roads
    road_patches = []
    divider_lines = []
    for road in roadnet['roads']:
        poly = get_road_geometry(road)
        if poly:
            road_patches.append(Polygon(poly, closed=True))
            divider_lines.extend(get_lane_divider_lines(road))
            
    p = PatchCollection(road_patches, facecolor=COLOR_ROAD, edgecolor=COLOR_LANE_BORDER, linewidth=1.2, zorder=2)
    ax_sim.add_collection(p)
    
    for l1, l2 in divider_lines:
        ax_sim.plot([l1[0], l2[0]], [l1[1], l2[1]], color=COLOR_LANE_DIVIDER, linewidth=0.8, linestyle='--', zorder=3)
        
    # Internal intersection guide links
    if inter:
        for road_link in inter.get('roadLinks', []):
            for lane_link in road_link.get('laneLinks', []):
                pts = [[pt['x'], pt['y']] for pt in lane_link.get('points', [])]
                if pts:
                    xs = [pt[0] for pt in pts]
                    ys = [pt[1] for pt in pts]
                    ax_sim.plot(xs, ys, color='#38bdf8', linewidth=0.7, alpha=0.22, linestyle=':', zorder=4)

    # Active phase evaluation
    display_log = current_log if current_log else last_log_entry
    action = display_log.get('action', 'ETWT') if display_log else 'ETWT'
    
    is_ET = (action == 'ETWT')
    is_WT = (action == 'ETWT')
    is_NT = (action == 'NTST')
    is_ST = (action == 'NTST')
    is_EL = (action == 'ELWL')
    is_WL = (action == 'ELWL')
    is_NL = (action == 'NLSL')
    is_SL = (action == 'NLSL')
    
    tl_config = [
        ('WT', cx - 18, cy + 4, is_WT),
        ('WL', cx - 18, cy + 9, is_WL),
        ('ET', cx + 18, cy - 4, is_ET),
        ('EL', cx + 18, cy - 9, is_EL),
        ('ST', cx - 4, cy - 18, is_ST),
        ('SL', cx - 9, cy - 18, is_SL),
        ('NT', cx + 4, cy + 18, is_NT),
        ('NL', cx + 9, cy + 18, is_NL)
    ]
    
    for name, tx, ty, is_green in tl_config:
        color = '#10b981' if is_green else '#ef4444'
        halo_color = '#059669' if is_green else '#b91c1c'
        ax_sim.add_patch(Circle((tx, ty), radius=3.2, color=halo_color, alpha=0.35, zorder=6))
        ax_sim.add_patch(Circle((tx, ty), radius=1.6, color=color, alpha=0.95, zorder=7))
        
        # Stop lines
        if 'W' in name:
            ax_sim.plot([cx - 15, cx - 15], [cy + 1, cy + 13], color='#e2e8f0', linewidth=2.0, alpha=0.8, zorder=5)
        elif 'E' in name:
            ax_sim.plot([cx + 15, cx + 15], [cy - 1, cy - 13], color='#e2e8f0', linewidth=2.0, alpha=0.8, zorder=5)
        elif 'S' in name:
            ax_sim.plot([cx - 1, cx - 13], [cy - 15, cy - 15], color='#e2e8f0', linewidth=2.0, alpha=0.8, zorder=5)
        elif 'N' in name:
            ax_sim.plot([cx + 1, cx + 13], [cy + 15, cy + 15], color='#e2e8f0', linewidth=2.0, alpha=0.8, zorder=5)

    # Intersection active flow trajectories
    if action == 'ETWT':
        ax_sim.annotate('', xy=(cx + 12, cy - 4), xytext=(cx - 12, cy - 4),
                        arrowprops=dict(arrowstyle='->', color='#10b981', lw=2.5, alpha=0.85), zorder=8)
        ax_sim.annotate('', xy=(cx - 12, cy + 4), xytext=(cx + 12, cy + 4),
                        arrowprops=dict(arrowstyle='->', color='#10b981', lw=2.5, alpha=0.85), zorder=8)
    elif action == 'NTST':
        ax_sim.annotate('', xy=(cx - 4, cy + 12), xytext=(cx - 4, cy - 12),
                        arrowprops=dict(arrowstyle='->', color='#10b981', lw=2.5, alpha=0.85), zorder=8)
        ax_sim.annotate('', xy=(cx + 4, cy - 12), xytext=(cx + 4, cy + 12),
                        arrowprops=dict(arrowstyle='->', color='#10b981', lw=2.5, alpha=0.85), zorder=8)
    elif action == 'ELWL':
        ax_sim.plot([cx - 10, cx - 2, cx - 2], [cy + 8, cy + 8, cy + 14], color='#10b981', lw=2.2, linestyle='-', zorder=8)
        ax_sim.plot([cx + 10, cx + 2, cx + 2], [cy - 8, cy - 8, cy - 14], color='#10b981', lw=2.2, linestyle='-', zorder=8)
    elif action == 'NLSL':
        ax_sim.plot([cx + 8, cx + 8, cx + 14], [cy + 10, cy + 2, cy + 2], color='#10b981', lw=2.2, linestyle='-', zorder=8)
        ax_sim.plot([cx - 8, cx - 8, cx - 14], [cy - 10, cy - 2, cy - 2], color='#10b981', lw=2.2, linestyle='-', zorder=8)

    # Vehicles
    vehicle_patches = []
    vehicle_colors = []
    for v in vehicles:
        w = v.get('width', 2.0)
        h = v.get('length', 4.8)
        vx, vy, angle = v['x'], v['y'], v['angle']
        draw_angle = angle
        dx, dy = h / 2, w / 2
        corners = [(-dx, -dy), (dx, -dy), (dx, dy), (-dx, dy)]
        c, s = np.cos(draw_angle), np.sin(draw_angle)
        rot_corners = [(vx + cx_off * c - cy_off * s, vy + cx_off * s + cy_off * c) for cx_off, cy_off in corners]
        vehicle_patches.append(Polygon(rot_corners, closed=True))
        vehicle_colors.append(get_vehicle_color(v['id']))

    vp = PatchCollection(vehicle_patches, facecolor=vehicle_colors, edgecolor='#ffffff', linewidth=0.5, alpha=0.95, zorder=6)
    ax_sim.add_collection(vp)
    
    # Sim View Overlays
    ax_sim.text(0.03, 0.96, '● LIVE SIMULATION', transform=ax_sim.transAxes,
                fontsize=11, fontweight='bold', color='#10b981', family='sans-serif', zorder=12,
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#111827', edgecolor='#10b981', alpha=0.9, lw=1))
    
    mins = step // 60
    secs = step % 60
    ax_sim.text(0.97, 0.96, f'STEP {step:04d}  |  TIME {mins:02d}:{secs:02d}  |  CARS: {len(vehicles)}',
                transform=ax_sim.transAxes, fontsize=10, fontweight='bold', color='#38bdf8', family='monospace',
                horizontalalignment='right', zorder=12,
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#111827', edgecolor='#1e293b', alpha=0.9, lw=1))
                
    ax_sim.text(0.03, 0.03, f'Node: {intersection_id}  •  Jinan Urban Corridor  •  CityFlow Engine',
                transform=ax_sim.transAxes, fontsize=9, color='#94a3b8', family='sans-serif', zorder=12,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#090d16', edgecolor='#1e293b', alpha=0.9))

    # ==========================================
    # Right Viewport: Telemetry & AI CoT Console
    # ==========================================
    ax_hud = fig.add_axes([0.65, 0.03, 0.33, 0.94])
    ax_hud.set_facecolor(COLOR_HUD_BG)
    ax_hud.axis('off')
    
    hud_border = FancyBboxPatch((0, 0), 1, 1, boxstyle='round,pad=0,rounding_size=0.02',
                                transform=ax_hud.transAxes,
                                edgecolor=COLOR_HUD_BORDER, facecolor=COLOR_HUD_BG, linewidth=1.5, zorder=1)
    ax_hud.add_patch(hud_border)
    
    # Header
    ax_hud.text(0.05, 0.955, 'TENSORCELL // TRAFFIC-R1', transform=ax_hud.transAxes,
                fontsize=15, fontweight='bold', color='#ffffff', family='sans-serif', zorder=2)
    ax_hud.text(0.05, 0.925, 'Autonomous Traffic Signal Agent  •  Qwen 2.5 CoT', transform=ax_hud.transAxes,
                fontsize=9.5, color='#38bdf8', family='sans-serif', zorder=2)
    ax_hud.plot([0.05, 0.95], [0.90, 0.90], transform=ax_hud.transAxes, color='#1e293b', lw=1.2, zorder=2)
    
    # Active Action Badge
    action_names = {
        'ETWT': 'EAST-WEST THROUGH (ETWT)',
        'NTST': 'NORTH-SOUTH THROUGH (NTST)',
        'ELWL': 'EAST-WEST LEFT-TURN (ELWL)',
        'NLSL': 'NORTH-SOUTH LEFT-TURN (NLSL)'
    }
    phase_title = action_names.get(action, f'PHASE: {action}')
    action_box = FancyBboxPatch((0.05, 0.815), 0.90, 0.068, boxstyle='round,pad=0.015,rounding_size=0.015',
                                transform=ax_hud.transAxes,
                                edgecolor='#10b981', facecolor='#064e3b', alpha=0.45, linewidth=1.5, zorder=2)
    ax_hud.add_patch(action_box)
    
    ax_hud.text(0.08, 0.828, f'●  {phase_title}', transform=ax_hud.transAxes,
                fontsize=11, fontweight='bold', color='#ffffff', family='sans-serif', zorder=3)
                
    # Directional Queue Gauges
    ax_hud.text(0.05, 0.78, 'INBOUND QUEUE CONGESTION & SENSORS', transform=ax_hud.transAxes,
                fontsize=9, fontweight='bold', color='#94a3b8', family='sans-serif', zorder=2)
                
    state = display_log.get('state', {}) if display_log else {}
    approaching_speed = display_log.get('approaching_speed', 0.0) if display_log else 0.0
    
    lanes = [
        ('West Through (WT)', state.get('WT', {}).get('queue_len', 0)),
        ('West Left (WL)', state.get('WL', {}).get('queue_len', 0)),
        ('East Through (ET)', state.get('ET', {}).get('queue_len', 0)),
        ('East Left (EL)', state.get('EL', {}).get('queue_len', 0)),
        ('North Through (NT)', state.get('NT', {}).get('queue_len', 0)),
        ('North Left (NL)', state.get('NL', {}).get('queue_len', 0)),
        ('South Through (ST)', state.get('ST', {}).get('queue_len', 0)),
        ('South Left (SL)', state.get('SL', {}).get('queue_len', 0)),
    ]
    
    y_start = 0.748
    bar_height = 0.017
    for i, (lname, qlen) in enumerate(lanes):
        y_pos = y_start - i * 0.0255
        ax_hud.text(0.05, y_pos, f'{lname:18s}', transform=ax_hud.transAxes,
                    fontsize=8, color='#cbd5e1', family='monospace', zorder=3)
        bg_bar = Rectangle((0.45, y_pos - 0.002), 0.40, bar_height, transform=ax_hud.transAxes,
                           facecolor='#1e293b', edgecolor='none', zorder=2)
        ax_hud.add_patch(bg_bar)
        
        bar_fill = min(qlen / 30.0, 1.0) * 0.40
        bar_color = '#10b981' if qlen < 5 else ('#f59e0b' if qlen < 15 else '#ef4444')
        if bar_fill > 0.005:
            fg_bar = Rectangle((0.45, y_pos - 0.002), bar_fill, bar_height, transform=ax_hud.transAxes,
                               facecolor=bar_color, edgecolor='none', zorder=3)
            ax_hud.add_patch(fg_bar)
        ax_hud.text(0.87, y_pos, f'{int(qlen):2d} cars', transform=ax_hud.transAxes,
                    fontsize=8, fontweight='bold', color=bar_color, family='monospace', zorder=3)

    # Speed & Congestion
    speed_y = y_start - 8 * 0.0255 - 0.015
    ax_hud.plot([0.05, 0.95], [speed_y + 0.015, speed_y + 0.015], transform=ax_hud.transAxes, color='#1e293b', lw=1.0, zorder=2)
    total_queued = sum([v.get('queue_len', 0) for v in state.values() if isinstance(v, dict)])
    ax_hud.text(0.05, speed_y - 0.005, f'Approaching Speed: {approaching_speed:.1f} m/s', transform=ax_hud.transAxes,
                fontsize=8.5, color='#38bdf8', family='sans-serif', fontweight='bold', zorder=3)
    ax_hud.text(0.55, speed_y - 0.005, f'Total Inbound Queue: {int(total_queued)} veh', transform=ax_hud.transAxes,
                fontsize=8.5, color='#f59e0b', family='sans-serif', fontweight='bold', zorder=3)

    # CoT Terminal Window
    cot_y = speed_y - 0.035
    ax_hud.text(0.05, cot_y, 'LLM REASONING TRACE (Chain-of-Thought)', transform=ax_hud.transAxes,
                fontsize=9, fontweight='bold', color='#94a3b8', family='sans-serif', zorder=2)
                
    cot_box = FancyBboxPatch((0.05, 0.075), 0.90, cot_y - 0.09, boxstyle='round,pad=0.01,rounding_size=0.01',
                            transform=ax_hud.transAxes,
                            edgecolor='#334155', facecolor='#090d16', linewidth=1.2, zorder=2)
    ax_hud.add_patch(cot_box)
    
    raw_response = display_log.get('response', '') if display_log else ''
    cleaned_resp = clean_llm_response(raw_response)
    
    lines = []
    for paragraph in cleaned_resp.split('\n'):
        if paragraph.strip():
            wrapped = textwrap.wrap(paragraph.strip(), width=52)
            lines.extend(wrapped)
            if len(lines) >= 11:
                break
                
    if not lines:
        lines = ['Model analyzing intersection traffic dynamics...']
        
    for j, line in enumerate(lines[:11]):
        line_color = '#38bdf8' if 'Signal:' in line or '<signal>' in line else ('#10b981' if 'optimal' in line.lower() or 'effective' in line.lower() else '#cbd5e1')
        ax_hud.text(0.07, (cot_y - 0.028) - j * 0.024, line, transform=ax_hud.transAxes,
                    fontsize=8.2, color=line_color, family='monospace', zorder=3)
                    
    # Footer
    ax_hud.plot([0.05, 0.95], [0.065, 0.065], transform=ax_hud.transAxes, color='#1e293b', lw=1.0, zorder=2)
    ax_hud.text(0.05, 0.035, 'Avg Delay: 8.0s/veh  •  Ideal Ratio: 1.017  •  Journeys: 8,606',
                transform=ax_hud.transAxes, fontsize=8.2, color='#64748b', family='monospace', zorder=3)
                
    canvas = FigureCanvas(fig)
    canvas.draw()
    
    try:
        img = np.frombuffer(canvas.buffer_rgba(), dtype='uint8')
    except AttributeError:
        try:
            img = np.frombuffer(canvas.tostring_argb(), dtype='uint8')
        except AttributeError:
            img = np.frombuffer(canvas.tostring_rgb(), dtype='uint8')
            
    width, height = canvas.get_width_height()
    plt.close(fig)
    
    if len(img) == width * height * 4:
        img = img.reshape(height, width, 4)
        return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR), display_log
    elif len(img) == width * height * 3:
        img = img.reshape(height, width, 3)
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR), display_log
    else:
        return None, display_log

def generate_video_programmatic(roadnet_file, replay_file, log_file, output_file, 
                                 steps=300, intersection_id='intersection_1_1', 
                                 interval=30, zoom_level=85, start_step=0, end_step=None):
    video = None
    try:
        if not os.path.exists(roadnet_file):
            return {'success': False, 'message': f'Roadnet file not found: {roadnet_file}', 'output_path': None}
        if not os.path.exists(replay_file):
            return {'success': False, 'message': f'Replay file not found: {replay_file}', 'output_path': None}
        if not os.path.exists(log_file):
            return {'success': False, 'message': f'Log file not found: {log_file}', 'output_path': None}
            
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Parsing inputs for cinematic 1080p render...')
        roadnet_data = parse_roadnet(roadnet_file)
        replay_lines = parse_replay(replay_file)
        full_logs = parse_logs(log_file)
        
        if end_step is None:
            end_step = min(start_step + steps, len(replay_lines))
        else:
            end_step = min(end_step, len(replay_lines))
            
        actual_steps = end_step - start_step
        if actual_steps <= 0:
            return {'success': False, 'message': f'Invalid step range: start={start_step}, end={end_step}', 'output_path': None}
            
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Rendering {actual_steps} frames (steps {start_step} to {end_step}) to {output_file}...')
        
        width, height = 1920, 1080
        fps = 60
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
        
        if not video.isOpened():
            return {'success': False, 'message': 'Failed to initialize cv2.VideoWriter with mp4v codec', 'output_path': None}
            
        last_log_entry = None
        
        def parse_vehicles_dict(line):
            v_dict = {}
            if not line: return v_dict
            parts = line.strip().split(';')
            if len(parts) > 0 and parts[0]:
                for c_str in parts[0].split(','):
                    c_data = c_str.split(' ')
                    if len(c_data) >= 7:
                        try:
                            vid = c_data[3]
                            v_dict[vid] = {
                                'id': vid,
                                'x': float(c_data[0]),
                                'y': float(c_data[1]),
                                'angle': float(c_data[2]),
                                'length': float(c_data[5]),
                                'width': float(c_data[6])
                            }
                        except: pass
            return v_dict

        def interp_angle(a1, a2, t):
            import math
            diff = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
            return a1 + diff * t

        frames_per_step = 12
        total_frames = actual_steps * frames_per_step
        frame_count = 0
        
        for i in range(start_step, end_step):
            line1 = replay_lines[i] if i < len(replay_lines) else ''
            line2 = replay_lines[i+1] if i+1 < len(replay_lines) else line1
            
            v1 = parse_vehicles_dict(line1)
            v2 = parse_vehicles_dict(line2)
            current_log = get_intersection_log(full_logs, intersection_id, i, interval, roadnet=roadnet_data[0])
            
            for f in range(frames_per_step):
                t = f / float(frames_per_step)
                vehicles_list = []
                for vid, veh1 in v1.items():
                    if vid in v2:
                        veh2 = v2[vid]
                        vehicles_list.append({
                            'id': vid,
                            'x': veh1['x'] + (veh2['x'] - veh1['x']) * t,
                            'y': veh1['y'] + (veh2['y'] - veh1['y']) * t,
                            'angle': interp_angle(veh1['angle'], veh2['angle'], t),
                            'length': veh1['length'],
                            'width': veh1['width']
                        })
                    else:
                        vehicles_list.append(veh1)
                
                for vid, veh2 in v2.items():
                    if vid not in v1 and t > 0.5:
                        vehicles_list.append(veh2)
                        
                frame, last_log_entry = draw_frame(roadnet_data, vehicles_list, [], current_log, 
                                                   i, intersection_id, last_log_entry, interval, zoom_level=zoom_level)
                                                   
                if frame is not None:
                    video.write(frame)
                
                frame_count += 1
                if frame_count % 50 == 0 or frame_count == total_frames:
                    print(f'[{datetime.now().strftime("%H:%M:%S")}] Rendered {frame_count}/{total_frames} frames ({int(frame_count/total_frames*100)}%)')
                    gc.collect()
                
        video.release()
        video = None
        
        file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Successfully created video: {output_file} ({file_size_mb:.2f} MB)')
        return {'success': True, 'message': f'Video generated successfully: {os.path.basename(output_file)}', 'output_path': output_file}
        
    except Exception as e:
        if video:
            video.release()
        traceback.print_exc()
        return {'success': False, 'message': str(e), 'output_path': None}

def main():
    parser = argparse.ArgumentParser(description='Generate cinematic 1080p portfolio video from CityFlow simulation.')
    parser.add_argument('--roadnet', required=True, help='Path to roadnet.json')
    parser.add_argument('--replay', required=True, help='Path to replay.txt')
    parser.add_argument('--log', required=True, help='Path to state_action.json')
    parser.add_argument('--output', default='output.mp4', help='Output video file path')
    parser.add_argument('--steps', type=int, default=300, help='Number of steps to render')
    parser.add_argument('--intersection', default='intersection_1_1', help='Intersection ID to focus on')
    parser.add_argument('--interval', type=int, default=30, help='Action interval')
    parser.add_argument('--zoom', type=float, default=85, help='Zoom level in meters')
    parser.add_argument('--start-step', type=int, default=0, help='Start step')
    parser.add_argument('--end-step', type=int, default=None, help='End step')
    
    args = parser.parse_args()
    res = generate_video_programmatic(
        args.roadnet, args.replay, args.log, args.output,
        steps=args.steps, intersection_id=args.intersection,
        interval=args.interval, zoom_level=args.zoom,
        start_step=args.start_step, end_step=args.end_step
    )
    if not res['success']:
        print('Error:', res['message'])
        exit(1)

if __name__ == '__main__':
    main()
