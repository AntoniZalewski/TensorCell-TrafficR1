import argparse
import json
import os
import cv2
import numpy as np

# CRITICAL: Set matplotlib backend to Agg BEFORE importing pyplot
# This prevents threading issues with tkinter backend
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, Circle, Wedge
from matplotlib.collections import PatchCollection
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from tqdm import tqdm
import math
import hashlib
import gc
import traceback

# Constants for visuals (matched with frontend)
COLOR_BG = '#e8ebed'
COLOR_ROAD = '#586970'
COLOR_LANE_DIVIDER = '#bed8e8' # Light blue-ish from frontend
COLOR_LANE_BORDER = '#82a8ba'
COLOR_TEXT_BG = '#ffffff'

# Vehicle colors from frontend
CAR_COLORS = [
    '#f2bfd7', # pink
    '#b7ebe4', # cyan
    '#dbebb7', # blue-ish green
    '#f5ddb5', # beige
    '#d4b5f5'  # purple
]

def parse_roadnet(roadnet_file):
    with open(roadnet_file, 'r') as f:
        roadnet = json.load(f)
    
    # Index roads by ID for easy lookup
    roads_dict = {r['id']: r for r in roadnet['roads']}
    intersections_dict = {i['id']: i for i in roadnet['intersections']}
    
    return roadnet, roads_dict, intersections_dict

def parse_replay(replay_file):
    with open(replay_file, 'r') as f:
        lines = f.readlines()
    return lines

def parse_logs(log_file):
    with open(log_file, 'r') as f:
        logs = json.load(f)
    return logs

def get_vehicle_color(vehicle_id):
    # Hash the vehicle ID to pick a color
    hash_val = int(hashlib.sha256(vehicle_id.encode('utf-8')).hexdigest(), 16)
    return CAR_COLORS[hash_val % len(CAR_COLORS)]

def get_road_geometry(road):
    # Calculate polygon for the road based on points and width
    # Points define the center line (or one edge, usually center in simplified models, 
    # but in CityFlow/Roadnet it's often the center of the road bundle or specific lane points).
    # Here we use the road points and total width.
    
    points = road['points']
    p1 = np.array([points[0]['x'], points[0]['y']])
    p2 = np.array([points[1]['x'], points[1]['y']])
    
    vec = p2 - p1
    length = np.linalg.norm(vec)
    if length == 0: return None
    
    direction = vec / length
    normal = np.array([-direction[1], direction[0]])
    
    # Calculate total width from lanes
    total_width = sum([l['width'] for l in road['lanes']])
    
    # In CityFlow roadnet, the points usually define the center of the road.
    # We draw a rectangle around this center line.
    
    c1 = p1 + normal * total_width / 2
    c2 = p1 - normal * total_width / 2
    c3 = p2 - normal * total_width / 2
    c4 = p2 + normal * total_width / 2
    
    return [c1, c2, c3, c4]

def get_lane_divider_lines(road):
    # Generate lines for lane dividers
    points = road['points']
    p1 = np.array([points[0]['x'], points[0]['y']])
    p2 = np.array([points[1]['x'], points[1]['y']])
    
    vec = p2 - p1
    length = np.linalg.norm(vec)
    if length == 0: return []
    
    direction = vec / length
    normal = np.array([-direction[1], direction[0]])
    
    total_width = sum([l['width'] for l in road['lanes']])
    current_width = -total_width / 2
    
    lines = []
    # We want dividers between lanes, so we iterate through lanes
    # Start from one side
    for i, lane in enumerate(road['lanes']):
        current_width += lane['width']
        if i < len(road['lanes']) - 1: # Don't draw on the very edge
            offset = normal * current_width
            l1 = p1 + offset
            l2 = p2 + offset
            lines.append((l1, l2))
            
    return lines

def draw_frame(roadnet_data, vehicles, traffic_lights, current_log, step, intersection_id, last_log_entry, action_interval):
    roadnet, roads_dict, intersections_dict = roadnet_data
    
    # Setup figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 14), gridspec_kw={'height_ratios': [3, 1]})
    fig.patch.set_facecolor(COLOR_BG)
    ax1.set_facecolor(COLOR_BG)
    
    # Focus on intersection
    inter = intersections_dict.get(intersection_id)
    if inter:
        cx, cy = inter['point']['x'], inter['point']['y']
        # Zoom out a bit to see approaching traffic
        ax1.set_xlim(cx - 100, cx + 100)
        ax1.set_ylim(cy - 100, cy + 100)
    else:
        ax1.set_xlim(-200, 200)
        ax1.set_ylim(-200, 200)
    
    ax1.set_aspect('equal')
    ax1.axis('off') # Hide axes
    
    # Title with step info
    sim_time = step # Assuming 1 step = 1 second usually, but let's just show step
    ax1.text(0.02, 0.98, f"Simulation Step: {step}", transform=ax1.transAxes, 
             fontsize=14, color='#333333', verticalalignment='top', fontweight='bold')

    # --- Draw Roads ---
    road_patches = []
    divider_lines = []
    
    # Draw all roads connected to the intersection (and maybe others if close?)
    # For now, draw all roads in the roadnet to be safe, or filter by distance if too slow.
    # Given the scale, drawing connected roads + their neighbors is usually enough.
    # Let's draw all for simplicity as the roadnet isn't huge.
    
    for road in roadnet['roads']:
        poly_points = get_road_geometry(road)
        if poly_points:
            road_patches.append(Polygon(poly_points, closed=True))
            divider_lines.extend(get_lane_divider_lines(road))
            
    # Draw intersection internal links (curves)
    # These are crucial for visual continuity
    if inter:
        for road_link in inter['roadLinks']:
            for lane_link in road_link['laneLinks']:
                pts = [[p['x'], p['y']] for p in lane_link['points']]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                ax1.plot(xs, ys, color=COLOR_LANE_DIVIDER, linewidth=1, alpha=0.5, linestyle='--')

    # Add road patches
    p = PatchCollection(road_patches, facecolor=COLOR_ROAD, edgecolor=COLOR_LANE_BORDER, linewidth=1, alpha=1.0)
    ax1.add_collection(p)
    
    # Draw dividers
    for l1, l2 in divider_lines:
        ax1.plot([l1[0], l2[0]], [l1[1], l2[1]], color=COLOR_LANE_DIVIDER, linewidth=1, linestyle='--')

    # --- Draw Vehicles ---
    vehicle_patches = []
    vehicle_colors = []
    
    for v in vehicles:
        w, h = 2.0, 5.0 # Approx size
        x, y, angle = v['x'], v['y'], v['angle']
        
        # Vehicle rotation
        # CityFlow angle is usually radians, 0 pointing North? Or East?
        # In the frontend script: rotation = 2 * Math.PI - parseFloat(carLog[2])
        # This implies standard CityFlow angle is inverted or needs adjustment.
        # Let's try standard rotation first.
        
        # Create rectangle centered at x,y rotated by angle
        # We compute corners manually
        dx = w / 2
        dy = h / 2
        
        # Corners relative to center
        corners = [(-dx, -dy), (dx, -dy), (dx, dy), (-dx, dy)]
        rotated_corners = []
        
        # Frontend uses: rotation = 2 * PI - angle. 
        # Let's try to match that logic. 
        # If CityFlow angle is 'a', we use -a (or 2pi - a).
        # Let's stick to the raw angle first, if it looks wrong we flip.
        # Actually, standard rotation matrix with 'angle' usually works if 'angle' is standard math angle.
        # If CityFlow uses bearing (0=North, CW), we need conversion.
        # Let's assume standard math for now (0=East, CCW) or adjust based on visual check.
        # Re-checking frontend: `carPool[i][0].rotation = 2 * Math.PI - parseFloat(carLog[2]);`
        # This suggests we should use -angle.
        
        draw_angle = -angle # + math.pi/2 # Maybe offset?
        
        c, s = np.cos(draw_angle), np.sin(draw_angle)
        
        for cx_off, cy_off in corners:
            rx = cx_off * c - cy_off * s
            ry = cx_off * s + cy_off * c
            rotated_corners.append((x + rx, y + ry))
            
        vehicle_patches.append(Polygon(rotated_corners, closed=True))
        vehicle_colors.append(get_vehicle_color(v['id']))

    vp = PatchCollection(vehicle_patches, facecolor=vehicle_colors, edgecolor='#555555', linewidth=0.5)
    ax1.add_collection(vp)

    # --- Draw Traffic Lights ---
    # Simplified: Draw dots at the end of incoming roads
    # We need traffic light state from logs or replay? 
    # Replay contains traffic light info! 
    # But for now, let's skip complex TL rendering as it requires mapping phases to lanes.
    
    # --- Draw LLM Reasoning ---
    ax2.axis('off')
    ax2.set_facecolor(COLOR_TEXT_BG)
    
    # Logic for persistent log
    # We update the log display only when a new action is taken (every 'interval' steps)
    # The 'current_log' passed here should be the one active for this step.
    
    display_log = current_log if current_log else last_log_entry
    
    if display_log:
        response = display_log.get('response', '')
        action = display_log.get('action', 'N/A')
        
        # Title for the reasoning box
        ax2.text(0.02, 0.90, "LLM Agent Reasoning", fontsize=16, fontweight='bold', color='#2c3e50', transform=ax2.transAxes)
        
        # Action
        ax2.text(0.02, 0.80, f"Selected Action: {action}", fontsize=14, fontweight='bold', color='#e74c3c', transform=ax2.transAxes)
        
        # Reasoning text
        text_content = f"{response}"
        
        # Wrap text
        import textwrap
        wrapped_text = textwrap.fill(text_content, width=80)
        
        ax2.text(0.02, 0.70, wrapped_text, fontsize=12, verticalalignment='top', 
                 fontfamily='monospace', transform=ax2.transAxes, color='#34495e')
    else:
        ax2.text(0.5, 0.5, "Waiting for first agent interaction...", fontsize=14, 
                 horizontalalignment='center', verticalalignment='center',
                 fontfamily='sans-serif', transform=ax2.transAxes, color='#95a5a6')

    # Convert to image
    canvas = FigureCanvas(fig)
    canvas.draw()
    
    # Handle different matplotlib versions
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
                                 steps=300, intersection_id="intersection_1_1", 
                                 interval=30, zoom_level=100, start_step=0, end_step=None):
    """
    Generate video programmatically from Python code.
    
    Args:
        roadnet_file: Path to roadnet JSON file
        replay_file: Path to replay TXT file
        log_file: Path to state_action.json file
        output_file: Path for output MP4 file
        steps: Number of steps to render (ignored if end_step is provided)
        intersection_id: ID of intersection to focus on (default: "intersection_1_1")
        interval: Action interval in steps (default: 30)
        zoom_level: Zoom level in meters (default: 100, smaller = more zoom)
        start_step: Starting step number (default: 0)
        end_step: Ending step number (default: None, uses start_step + steps)
    
    Returns:
        dict: {'success': bool, 'message': str, 'output_path': str}
    """
    video = None  # Initialize for cleanup
    try:
        import os
        from datetime import datetime
        
        # Validate input files
        if not os.path.exists(roadnet_file):
            return {'success': False, 'message': f'Roadnet file not found: {roadnet_file}', 'output_path': None}
        if not os.path.exists(replay_file):
            return {'success': False, 'message': f'Replay file not found: {replay_file}', 'output_path': None}
        if not os.path.exists(log_file):
            return {'success': False, 'message': f'Log file not found: {log_file}', 'output_path': None}
        
        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading data...")
        roadnet_data = parse_roadnet(roadnet_file)
        replay_lines = parse_replay(replay_file)
        full_logs = parse_logs(log_file)
        
        # Calculate actual end step
        if end_step is None:
            end_step = min(start_step + steps, len(replay_lines))
        else:
            end_step = min(end_step, len(replay_lines))
        
        actual_steps = end_step - start_step
        
        if actual_steps <= 0:
            return {'success': False, 'message': f'Invalid step range: start={start_step}, end={end_step}', 'output_path': None}
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Rendering steps {start_step} to {end_step} ({actual_steps} frames)")
        
        # Prepare video writer with custom zoom
        def draw_frame_with_zoom(roadnet_data, vehicles, traffic_lights, current_log, step, intersection_id, last_log_entry, action_interval):
            roadnet, roads_dict, intersections_dict = roadnet_data
            
            # Setup figure
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 14), gridspec_kw={'height_ratios': [3, 1]})
            fig.patch.set_facecolor(COLOR_BG)
            ax1.set_facecolor(COLOR_BG)
            
            # Focus on intersection with custom zoom
            inter = intersections_dict.get(intersection_id)
            if inter:
                cx, cy = inter['point']['x'], inter['point']['y']
                # Use zoom_level parameter
                ax1.set_xlim(cx - zoom_level, cx + zoom_level)
                ax1.set_ylim(cy - zoom_level, cy + zoom_level)
            else:
                ax1.set_xlim(-200, 200)
                ax1.set_ylim(-200, 200)
            
            ax1.set_aspect('equal')
            ax1.axis('off')
            
            # Title with step info
            ax1.text(0.02, 0.98, f"Simulation Step: {step}", transform=ax1.transAxes, 
                     fontsize=14, color='#333333', verticalalignment='top', fontweight='bold')

            # Draw Roads
            road_patches = []
            divider_lines = []
            
            for road in roadnet['roads']:
                poly_points = get_road_geometry(road)
                if poly_points:
                    road_patches.append(Polygon(poly_points, closed=True))
                    divider_lines.extend(get_lane_divider_lines(road))
            
            # Draw intersection internal links
            if inter:
                for road_link in inter['roadLinks']:
                    for lane_link in road_link['laneLinks']:
                        pts = [[p['x'], p['y']] for p in lane_link['points']]
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                        ax1.plot(xs, ys, color=COLOR_LANE_DIVIDER, linewidth=1, alpha=0.5, linestyle='--')

            # Add road patches
            p = PatchCollection(road_patches, facecolor=COLOR_ROAD, edgecolor=COLOR_LANE_BORDER, linewidth=1, alpha=1.0)
            ax1.add_collection(p)
            
            # Draw dividers
            for l1, l2 in divider_lines:
                ax1.plot([l1[0], l2[0]], [l1[1], l2[1]], color=COLOR_LANE_DIVIDER, linewidth=1, linestyle='--')

            # Draw Vehicles
            vehicle_patches = []
            vehicle_colors = []
            
            for v in vehicles:
                # Use actual vehicle dimensions from data
                # Frontend: width = v_data[6], length = v_data[5]
                w = v.get('width', 2.0)
                h = v.get('length', 5.0)
                x, y, angle = v['x'], -v['y'], v['angle']  # Y-axis flip to match frontend
                
                # Match frontend rotation: 2*PI - angle
                draw_angle = 2 * np.pi - angle
                
                dx = w / 2
                dy = h / 2
                
                corners = [(-dx, -dy), (dx, -dy), (dx, dy), (-dx, dy)]
                rotated_corners = []
                
                c, s = np.cos(draw_angle), np.sin(draw_angle)
                
                for cx_off, cy_off in corners:
                    rx = cx_off * c - cy_off * s
                    ry = cx_off * s + cy_off * c
                    rotated_corners.append((x + rx, y + ry))
                    
                vehicle_patches.append(Polygon(rotated_corners, closed=True))
                vehicle_colors.append(get_vehicle_color(v['id']))

            vp = PatchCollection(vehicle_patches, facecolor=vehicle_colors, edgecolor='#555555', linewidth=0.5)
            ax1.add_collection(vp)

            # Draw LLM Reasoning
            ax2.axis('off')
            ax2.set_facecolor(COLOR_TEXT_BG)
            
            display_log = current_log if current_log else last_log_entry
            
            if display_log:
                response = display_log.get('response', '')
                action = display_log.get('action', 'N/A')
                
                ax2.text(0.02, 0.90, "LLM Agent Reasoning", fontsize=16, fontweight='bold', color='#2c3e50', transform=ax2.transAxes)
                ax2.text(0.02, 0.80, f"Selected Action: {action}", fontsize=14, fontweight='bold', color='#e74c3c', transform=ax2.transAxes)
                
                text_content = f"{response}"
                
                import textwrap
                wrapped_text = textwrap.fill(text_content, width=80)
                
                ax2.text(0.02, 0.70, wrapped_text, fontsize=12, verticalalignment='top', 
                         fontfamily='monospace', transform=ax2.transAxes, color='#34495e')
            else:
                ax2.text(0.5, 0.5, "Waiting for first agent interaction...", fontsize=14, 
                         horizontalalignment='center', verticalalignment='center',
                         fontfamily='sans-serif', transform=ax2.transAxes, color='#95a5a6')

            # Convert to image
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
        
        # Create dummy frame
        dummy_frame, _ = draw_frame_with_zoom(roadnet_data, [], [], None, 0, intersection_id, None, interval)
        if dummy_frame is None:
            return {'success': False, 'message': 'Error creating dummy frame', 'output_path': None}

        height, width, layers = dummy_frame.shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video = cv2.VideoWriter(output_file, fourcc, 10, (width, height))
        
        last_log_entry = None
        frames_written = 0
        
        # DEBUG: Check data
        print(f"[DEBUG] Total replay lines: {len(replay_lines)}")
        print(f"[DEBUG] Total log entries: {len(full_logs)}")
        print(f"[DEBUG] Rendering range: {start_step} to {end_step}")
        
        # Test parse first few lines
        for test_i in [start_step, start_step + 100, min(start_step + 500, end_step - 1)]:
            if test_i < len(replay_lines):
                test_line = replay_lines[test_i].strip()
                test_parts = test_line.split(';')
                test_vehicle_part = test_parts[0] if len(test_parts) > 0 else ""
                test_vehicles = test_vehicle_part.split(',') if test_vehicle_part else []
                print(f"[DEBUG] Step {test_i}: {len(test_vehicles)} vehicle strings in line")
                if len(test_vehicles) > 0 and test_vehicles[0]:
                    print(f"[DEBUG]   First vehicle: {test_vehicles[0][:80]}")
        
        for i in tqdm(range(start_step, end_step)):
            try:
                line = replay_lines[i].strip()
                if not line: continue
                
                # Parse replay line
                parts = line.split(';')
                vehicle_part = parts[0]
                
                vehicles = []
                if vehicle_part:
                    vehicle_strings = vehicle_part.split(',')
                    for v_str in vehicle_strings:
                        v_data = v_str.split(' ')
                        # Format: x y angle id laneChange length width
                        if len(v_data) >= 7:
                            try:
                                vehicles.append({
                                    'id': v_data[3],  # ID is 4th element
                                    'x': float(v_data[0]),  # X is 1st
                                    'y': float(v_data[1]),  # Y is 2nd
                                    'angle': float(v_data[2]),  # Angle is 3rd
                                    'length': float(v_data[5]),  # Length is 6th
                                    'width': float(v_data[6])  # Width is 7th
                                })
                            except (ValueError, IndexError):
                                pass

                log_index = i // interval
                current_log = None
                
                if log_index < len(full_logs):
                    entry = full_logs[log_index]
                    if isinstance(entry, list):
                        if len(entry) > 0:
                            current_log = entry[0]
                    else:
                        current_log = entry
                
                # DEBUG: Log every 100 steps
                if i % 100 == 0:
                    print(f"[DEBUG] Step {i}: {len(vehicles)} vehicles parsed, log_index={log_index}, has_log={current_log is not None}")
                
                frame, last_log_entry = draw_frame_with_zoom(roadnet_data, vehicles, [], current_log, i, intersection_id, last_log_entry, interval)
                
                if frame is not None:
                    video.write(frame)
                    frames_written += 1
                
                # More aggressive cleanup for long renders
                plt.close('all')
                if i % 5 == 0:  # More frequent cleanup
                    gc.collect()
                    
            except Exception as e:
                print(f"[WARNING] Error at frame {i}: {str(e)}")
                # Continue rendering, don't fail completely
                continue
        
        video.release()
        video = None  # Mark as released
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Video saved to {output_file} ({frames_written} frames)")
        
        return {'success': True, 'message': f'Video generated successfully ({frames_written} frames)', 'output_path': output_file}
        
    except Exception as e:
        error_msg = f"Error generating video: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        
        # Try to save partial video if any frames were written
        if video is not None:
            try:
                video.release()
                print("[INFO] Partial video saved before crash")
            except:
                pass
        
        return {'success': False, 'message': error_msg, 'output_path': None}


def main():
    parser = argparse.ArgumentParser(description="Generate video from CityFlow replay and LLM logs")
    parser.add_argument('--roadnet', type=str, required=True, help="Path to roadnet JSON")
    parser.add_argument('--replay', type=str, required=True, help="Path to replay TXT")
    parser.add_argument('--log', type=str, required=True, help="Path to state_action.json")
    parser.add_argument('--output', type=str, required=True, help="Output MP4 file")
    parser.add_argument('--steps', type=int, default=300, help="Number of steps to render (used if --end not specified)")
    parser.add_argument('--start', type=int, default=0, help="Starting step number (default: 0)")
    parser.add_argument('--end', type=int, default=None, help="Ending step number (default: start + steps)")
    parser.add_argument('--intersection', type=str, default="intersection_1_1", help="Intersection ID")
    parser.add_argument('--interval', type=int, default=30, help="Action interval (steps)")
    parser.add_argument('--zoom', type=int, default=100, help="Zoom level in meters (smaller = more zoom)")
    
    args = parser.parse_args()
    
    # Use programmatic function
    result = generate_video_programmatic(
        args.roadnet, args.replay, args.log, args.output,
        steps=args.steps, start_step=args.start, end_step=args.end,
        intersection_id=args.intersection,
        interval=args.interval, zoom_level=args.zoom
    )
    
    if not result['success']:
        print(f"Failed: {result['message']}")
        exit(1)

if __name__ == "__main__":
    main()
